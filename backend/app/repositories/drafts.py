from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import AIResult, OzonDraft
from app.schemas.drafts import DraftUpdate


class DraftRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, draft_id: int) -> OzonDraft:
        draft = self.session.scalar(
            select(OzonDraft)
            .options(selectinload(OzonDraft.ai_result), selectinload(OzonDraft.product))
            .where(OzonDraft.id == draft_id)
        )
        if draft is None:
            raise NotFoundError(f"Ozon 草稿 {draft_id} 不存在")
        return draft

    def list(self, status: str | None = None, limit: int = 100) -> tuple[Sequence[OzonDraft], int]:
        filters = [OzonDraft.status == status] if status else []
        total = self.session.scalar(select(func.count(OzonDraft.id)).where(*filters)) or 0
        drafts = self.session.scalars(
            select(OzonDraft)
            .options(selectinload(OzonDraft.ai_result), selectinload(OzonDraft.product))
            .where(*filters)
            .order_by(OzonDraft.updated_at.desc(), OzonDraft.id.desc())
            .limit(limit)
        ).all()
        return drafts, total

    def upsert_pending(
        self,
        *,
        product_id: int,
        ai_result: AIResult,
        title: str,
        description: str,
        category_id: str,
        attributes: dict[str, object],
        variants: list[dict[str, object]],
        images: list[str],
        pricing: dict[str, object],
        price: Decimal,
        stock: int,
    ) -> OzonDraft:
        draft = self.session.scalar(
            select(OzonDraft)
            .where(
                OzonDraft.product_id == product_id,
                OzonDraft.status.in_(["review", "draft"]),
            )
            .order_by(OzonDraft.created_at.desc())
        )
        if draft is None:
            draft = OzonDraft(product_id=product_id, title=title, description=description,
                              category_id=category_id, price=price)
            self.session.add(draft)
        draft.ai_result = ai_result
        draft.title = title
        draft.description = description
        draft.category_id = category_id
        draft.attributes = attributes
        draft.variants = variants
        draft.images = images
        draft.pricing = pricing
        draft.price = price
        draft.stock = stock
        draft.status = "review"
        self.session.commit()
        return self.get(draft.id)

    def update(self, draft_id: int, update: DraftUpdate) -> OzonDraft:
        draft = self.get(draft_id)
        if draft.status == "published":
            raise ConflictError("已发布的草稿不能再修改")
        if draft.status == "stale":
            raise ConflictError("源商品已发生变化，请重新进行 AI 加工后再编辑草稿")
        changes = update.model_dump(exclude_unset=True)
        mapping = {
            "title_ru": "title",
            "description_ru": "description",
            "skus": "variants",
            "suggested_price": "price",
        }
        for field, value in changes.items():
            if field in {"suggested_price", "stock", "skus"}:
                continue
            target = mapping.get(field, field)
            setattr(draft, target, value)

        if "skus" in changes:
            updated_variants = [
                {**dict(item), "price": float(draft.price)}
                for item in changes["skus"]
            ]
            sku_stock = sum(
                max(0, int(item.get("stock", 0))) for item in updated_variants
            )
            if "stock" in changes and int(changes["stock"]) != sku_stock:
                raise ValidationError("草稿总库存必须等于所有 SKU 库存之和")
            draft.variants = updated_variants
            draft.stock = sku_stock

        if "suggested_price" in changes:
            draft.price = Decimal(str(changes["suggested_price"]))
            draft.pricing = self._recalculate_pricing(draft.pricing, draft.price)
            draft.variants = [
                {**item, "price": float(draft.price)} for item in draft.variants
            ]

        if "stock" in changes and "skus" not in changes:
            draft.stock = int(changes["stock"])
            draft.variants = self._distribute_stock(draft.variants, draft.stock)

        draft.status = "review"
        self.session.commit()
        return self.get(draft_id)

    @staticmethod
    def _recalculate_pricing(
        current: dict[str, object], sale_price: Decimal
    ) -> dict[str, object]:
        pricing = dict(current)
        fixed_cost = Decimal(str(pricing.get("fixed_cost_rub", 0)))
        variable_rate = Decimal(str(pricing.get("variable_cost_rate", 0)))
        total_cost = fixed_cost + sale_price * variable_rate
        profit = sale_price - total_cost
        margin = profit / sale_price
        money = Decimal("0.01")
        pricing.update(
            {
                "suggested_price_rub": float(sale_price.quantize(money, ROUND_HALF_UP)),
                "estimated_total_cost_rub": float(total_cost.quantize(money, ROUND_HALF_UP)),
                "estimated_profit_rub": float(profit.quantize(money, ROUND_HALF_UP)),
                "estimated_profit_margin": float(
                    margin.quantize(Decimal("0.0001"), ROUND_HALF_UP)
                ),
            }
        )
        return pricing

    @staticmethod
    def _distribute_stock(
        variants: list[dict[str, object]], total_stock: int
    ) -> list[dict[str, object]]:
        if not variants:
            return variants
        quotient, remainder = divmod(total_stock, len(variants))
        return [
            {**item, "stock": quotient + (1 if index < remainder else 0)}
            for index, item in enumerate(variants)
        ]

    def save(self, draft: OzonDraft) -> OzonDraft:
        self.session.commit()
        return self.get(draft.id)

