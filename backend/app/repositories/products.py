import hashlib
import math
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.database.base import utc_now
from app.integrations.sources.base import NormalizedProductData
from app.integrations.sources.provenance import source_data_kind
from app.models import AIResult, OzonDraft, Product, SourceProduct, Variant
from app.schemas.products import ProductUpdate


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _with_relations(statement: Select[tuple[Product]]) -> Select[tuple[Product]]:
        return statement.options(
            selectinload(Product.source_product),
            selectinload(Product.variants),
            selectinload(Product.ai_results),
            selectinload(Product.drafts).selectinload(OzonDraft.ai_result),
        )

    def get(self, product_id: int) -> Product:
        statement = self._with_relations(
            select(Product)
            .where(Product.id == product_id)
            .execution_options(populate_existing=True)
        )
        product = self.session.scalar(statement)
        if product is None:
            raise NotFoundError(f"商品 {product_id} 不存在")
        return product

    def list(
        self,
        *,
        search: str | None,
        ai_status: str | None,
        ozon_status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Product], int, int]:
        filters = []
        if search:
            keyword = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Product.title_original).like(keyword),
                    func.lower(func.coalesce(Product.supplier, "")).like(keyword),
                    Product.source_product.has(
                        func.lower(SourceProduct.source_product_id).like(keyword)
                    ),
                )
            )
        if ai_status:
            filters.append(Product.ai_status == ai_status)
        if ozon_status:
            if ozon_status in {"draft", "review", "stale", "published"}:
                filters.append(Product.drafts.any(OzonDraft.status == ozon_status))
            else:
                filters.append(Product.ozon_status == ozon_status)

        total = self.session.scalar(select(func.count(Product.id)).where(*filters)) or 0
        pages = math.ceil(total / page_size) if total else 0
        statement = (
            self._with_relations(select(Product).where(*filters))
            .order_by(Product.created_at.desc(), Product.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return self.session.scalars(statement).all(), total, pages

    def recent(self, limit: int = 5) -> Sequence[Product]:
        statement = (
            self._with_relations(select(Product))
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(limit)
        )
        return self.session.scalars(statement).all()

    def save_collected(self, data: NormalizedProductData) -> Product:
        try:
            return self._save_collected(data)
        except Exception:
            self.session.rollback()
            raise

    def _save_collected(self, data: NormalizedProductData) -> Product:
        self._separate_legacy_mock(data.source_product_id)
        source = self.session.scalar(
            select(SourceProduct).where(
                SourceProduct.source == data.source,
                SourceProduct.source_product_id == data.source_product_id,
            )
        )
        if source is None:
            source = SourceProduct(
                source=data.source,
                source_product_id=data.source_product_id,
                source_url=str(data.source_url),
                raw_payload=data.raw_payload,
            )
            self.session.add(source)
            self.session.flush()
        else:
            source.source_url = str(data.source_url)
            source.raw_payload = data.raw_payload
            source.fetched_at = utc_now()

        product = self.session.scalar(select(Product).where(Product.source_product_id == source.id))
        if product is None:
            product = Product(source_product=source, purchase_price=Decimal("0"))
            self.session.add(product)
            source_facts_changed = False
        else:
            source_facts_changed = self._collected_facts(product) != self._incoming_facts(data)
            if source_facts_changed:
                self._invalidate_downstream(product)
        self._apply_normalized(product, data)
        existing_variants = {
            variant.source_sku_id: variant for variant in product.variants
        }
        incoming_variant_ids = {item.source_sku_id for item in data.variants}
        for variant in list(product.variants):
            if variant.source_sku_id not in incoming_variant_ids:
                product.variants.remove(variant)
        for item in data.variants:
            variant = existing_variants.get(item.source_sku_id)
            if variant is None:
                digest = hashlib.sha1(
                    (
                        f"v2:{data.source}:{data.source_product_id}:"
                        f"{item.source_sku_id}"
                    ).encode("utf-8"),
                    usedforsecurity=False,
                ).hexdigest()[:12].upper()
                variant = Variant(
                    source_sku_id=item.source_sku_id,
                    internal_sku=f"OA-{digest}",
                )
                product.variants.append(variant)
            variant.name = item.name
            variant.color = item.color
            variant.size = item.size
            variant.purchase_price = Decimal(str(item.purchase_price))
            variant.stock = item.stock
            variant.image = item.image
        self.session.commit()
        return self.get(product.id)

    def _separate_legacy_mock(self, offer_id: str) -> None:
        """Keep pre-provenance fixtures intact when a real offer is collected."""

        legacy_source = self.session.scalar(
            select(SourceProduct).where(
                SourceProduct.source == "1688",
                SourceProduct.source_product_id == offer_id,
            )
        )
        if legacy_source is None or source_data_kind("1688", legacy_source.raw_payload) != "mock":
            return
        collision = self.session.scalar(
            select(SourceProduct).where(
                SourceProduct.source == "mock_1688",
                SourceProduct.source_product_id == offer_id,
            )
        )
        if collision is not None:
            raise ConflictError("存在重复的历史模拟商品，采集未保存。请先在商品库处理重复的模拟样例。")
        legacy_source.source = "mock_1688"
        legacy_source.raw_payload = {
            **legacy_source.raw_payload,
            "provider": "mock_1688",
            "mock": True,
            "source": "mock_1688",
        }
        self.session.flush()

    @staticmethod
    def _apply_normalized(product: Product, data: NormalizedProductData) -> None:
        product.title_original = data.title_original
        product.description_original = data.description_original
        product.category_original = data.category_original
        product.supplier = data.supplier
        product.purchase_price = Decimal(str(data.purchase_price))
        product.currency = data.currency
        product.images = data.images
        product.videos = data.videos
        product.attributes = data.attributes
        product.stock = data.stock
        product.weight_kg = Decimal(str(data.weight_kg)) if data.weight_kg else None
        product.dimensions_cm = data.dimensions_cm

    def update(self, product_id: int, update: ProductUpdate) -> Product:
        product = self.get(product_id)
        changes = update.model_dump(exclude_unset=True)
        if "purchase_price" in changes:
            changes["purchase_price"] = Decimal(str(changes["purchase_price"]))
        if "weight_kg" in changes and changes["weight_kg"] is not None:
            changes["weight_kg"] = Decimal(str(changes["weight_kg"]))
        if any(getattr(product, field) != value for field, value in changes.items()):
            self._invalidate_downstream(product)
        if "stock" in changes and product.variants:
            quotient, remainder = divmod(int(changes["stock"]), len(product.variants))
            for index, variant in enumerate(product.variants):
                variant.stock = quotient + (1 if index < remainder else 0)
        for field, value in changes.items():
            setattr(product, field, value)
        self.session.commit()
        return self.get(product_id)

    @staticmethod
    def _invalidate_downstream(product: Product) -> None:
        for draft in product.drafts:
            if draft.status != "published":
                draft.status = "stale"
        product.ai_status = "pending"
        product.ozon_status = (
            "published" if any(draft.status == "published" for draft in product.drafts) else "not_created"
        )
        product.estimated_price = None
        product.estimated_profit_margin = None

    @staticmethod
    def _collected_facts(product: Product) -> dict[str, object]:
        return {
            "title_original": product.title_original,
            "description_original": product.description_original,
            "category_original": product.category_original,
            "supplier": product.supplier,
            "purchase_price": float(product.purchase_price),
            "currency": product.currency,
            "images": product.images,
            "videos": product.videos,
            "attributes": product.attributes,
            "stock": product.stock,
            "weight_kg": float(product.weight_kg) if product.weight_kg is not None else None,
            "dimensions_cm": product.dimensions_cm,
            "variants": [
                {
                    "source_sku_id": item.source_sku_id,
                    "name": item.name,
                    "color": item.color,
                    "size": item.size,
                    "purchase_price": float(item.purchase_price),
                    "stock": item.stock,
                    "image": item.image,
                }
                for item in sorted(
                    product.variants, key=lambda variant: variant.source_sku_id
                )
            ],
        }

    @staticmethod
    def _incoming_facts(data: NormalizedProductData) -> dict[str, object]:
        return {
            "title_original": data.title_original,
            "description_original": data.description_original,
            "category_original": data.category_original,
            "supplier": data.supplier,
            "purchase_price": float(data.purchase_price),
            "currency": data.currency,
            "images": data.images,
            "videos": data.videos,
            "attributes": data.attributes,
            "stock": data.stock,
            "weight_kg": float(data.weight_kg) if data.weight_kg is not None else None,
            "dimensions_cm": data.dimensions_cm,
            "variants": [
                {
                    "source_sku_id": item.source_sku_id,
                    "name": item.name,
                    "color": item.color,
                    "size": item.size,
                    "purchase_price": float(item.purchase_price),
                    "stock": item.stock,
                    "image": item.image,
                }
                for item in sorted(
                    data.variants, key=lambda variant: variant.source_sku_id
                )
            ],
        }

    def add_ai_result(self, result: AIResult) -> AIResult:
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        return result

    def save_status(
        self,
        product: Product,
        *,
        ai_status: str | None = None,
        ozon_status: str | None = None,
        estimated_price: Decimal | None = None,
        estimated_profit_margin: Decimal | None = None,
    ) -> None:
        if ai_status is not None:
            product.ai_status = ai_status
        if ozon_status is not None:
            product.ozon_status = ozon_status
        if estimated_price is not None:
            product.estimated_price = estimated_price
        if estimated_profit_margin is not None:
            product.estimated_profit_margin = estimated_profit_margin
        self.session.commit()

    def delete(self, product_id: int) -> None:
        product = self.get(product_id)
        self.session.delete(product.source_product)
        self.session.commit()

    def counts(self) -> dict[str, int]:
        product_total = self.session.scalar(select(func.count(Product.id))) or 0
        pending_ai = (
            self.session.scalar(
                select(func.count(Product.id)).where(Product.ai_status.in_(["pending", "failed"]))
            )
            or 0
        )
        pending_review = self.session.scalar(
            select(func.count(func.distinct(OzonDraft.product_id))).where(
                OzonDraft.status == "review"
            )
        ) or 0
        published = self.session.scalar(
            select(func.count(func.distinct(OzonDraft.product_id))).where(
                OzonDraft.status == "published"
            )
        ) or 0
        return {
            "product_total": product_total,
            "pending_ai": pending_ai,
            "pending_review": pending_review,
            "published": published,
        }

