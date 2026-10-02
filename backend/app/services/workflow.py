from decimal import Decimal
from typing import Any, Literal

from app.core.errors import ConflictError, IntegrationError, ValidationError
from app.core.security import sanitize_for_log
from app.database.base import utc_now
from app.integrations.ai import AIGateway
from app.integrations.ozon import MockOzonConnector, OzonAttributeMapper, OzonCategoryMapper, OzonConnector
from app.integrations.sources import ProductSourceAdapter
from app.integrations.sources.provenance import source_data_kind, source_data_provider
from app.models import AIResult, OzonDraft, Product
from app.pricing import PricingEngine, PricingInput
from app.repositories.drafts import DraftRepository
from app.repositories.logs import LogRepository
from app.repositories.products import ProductRepository
from app.repositories.tasks import TaskRepository
from app.schemas.drafts import DraftUpdate
from app.services.tasks import TaskService


class ProductWorkflowService:
    def __init__(
        self,
        *,
        products: ProductRepository,
        drafts: DraftRepository,
        tasks: TaskRepository,
        logs: LogRepository,
        source_adapter: ProductSourceAdapter,
        collection_mode: Literal["real", "mock"],
        ai_gateway: AIGateway,
        category_mapper: OzonCategoryMapper,
        attribute_mapper: OzonAttributeMapper,
        pricing_engine: PricingEngine,
        pricing_options: dict[str, Decimal],
        ozon_connector: OzonConnector,
    ) -> None:
        self.products = products
        self.drafts = drafts
        self.task_service = TaskService(tasks)
        self.logs = logs
        self.source_adapter = source_adapter
        self.collection_mode = collection_mode
        self.ai_gateway = ai_gateway
        self.category_mapper = category_mapper
        self.attribute_mapper = attribute_mapper
        self.pricing_engine = pricing_engine
        self.pricing_options = pricing_options
        self.ozon_connector = ozon_connector

    def collect(self, url: str) -> tuple[Product, int]:
        mode_context = {"collection_mode": self.collection_mode, "mock": self.collection_mode == "mock"}
        task = self.task_service.create("collect_product", {"url": url, "source": "1688", **mode_context})
        self.task_service.start(task, progress=10)
        try:
            normalized = self.source_adapter.collect(url)
            if source_data_kind(normalized.source, normalized.raw_payload) != self.collection_mode:
                raise IntegrationError("采集数据来源与所选模式不一致，未保存商品")
            self.task_service.set_progress(task, 60)
            product = self.products.save_collected(normalized)
            self.task_service.succeed(
                task,
                {"product_id": product.id, "source_product_id": normalized.source_product_id, **mode_context},
            )
            self.logs.add(
                "INFO",
                "1688",
                "模拟商品采集成功" if self.collection_mode == "mock" else "真实商品采集成功",
                {"product_id": product.id, "source_product_id": normalized.source_product_id, **mode_context},
            )
            return product, task.id
        except Exception as exc:
            self.task_service.fail(task, exc)
            self.logs.add("ERROR", "1688", "商品采集失败", {"error": str(exc), "url": url, **mode_context})
            raise

    def process(self, product_id: int) -> tuple[Product, OzonDraft, int]:
        product = self.products.get(product_id)
        has_published_draft = any(
            draft.status == "published" for draft in product.drafts
        )
        data_kind = source_data_kind(product.source_product.source, product.source_product.raw_payload)
        processing_context = {"data_kind": data_kind, "mock": self.ai_gateway.provider.name == "mock"}
        task = self.task_service.create("process_product", {"product_id": product_id, **processing_context})
        self.task_service.start(task, progress=5)
        self.products.save_status(product, ai_status="processing")
        ai_input = self._ai_input(product)
        try:
            try:
                if data_kind == "real" and self.ai_gateway.provider.name == "mock":
                    raise ConflictError("真实商品不能使用模拟 AI 加工。请先接入真实 AI 服务；商品原始数据已保留，未生成虚拟俄语内容或草稿。")
                generation = self.ai_gateway.process_product(ai_input)
            except Exception as exc:
                self.products.add_ai_result(
                    AIResult(
                        product=product,
                        provider=self.ai_gateway.provider.name,
                        model=self.ai_gateway.provider.model,
                        status="failed",
                        input_payload=ai_input,
                        output_payload={},
                        title_ru="",
                        description_ru="",
                        category_suggestion="",
                        category_confidence=Decimal("0"),
                        attributes_suggestion={},
                        risk_level="high",
                        risk_checks=[],
                        error=str(sanitize_for_log(str(exc))),
                    )
                )
                raise
            self.task_service.set_progress(task, 45)
            output = generation.output
            ai_result = self.products.add_ai_result(
                AIResult(
                    product=product,
                    provider=generation.provider,
                    model=generation.model,
                    status="success",
                    input_payload=ai_input,
                    output_payload=output.model_dump(mode="json"),
                    title_ru=output.title_ru,
                    description_ru=output.description_ru,
                    category_suggestion=output.category_suggestion,
                    category_confidence=Decimal(str(output.category_confidence)),
                    attributes_suggestion=output.attributes_suggestion,
                    risk_level=output.risk_level,
                    risk_checks=[check.model_dump() for check in output.risk_checks],
                    token_usage=generation.token_usage,
                    latency_ms=generation.latency_ms,
                )
            )
            category_id, _ = self.category_mapper.map(output)
            attributes = self.attribute_mapper.map(output)
            pricing_purchase_price = max(
                [
                    product.purchase_price,
                    *(variant.purchase_price for variant in product.variants),
                ]
            )
            pricing = self.pricing_engine.calculate(
                PricingInput(
                    purchase_price_cny=pricing_purchase_price,
                    **self.pricing_options,
                )
            )
            self.task_service.set_progress(task, 75)
            pricing_payload = {
                key: float(value) if isinstance(value, Decimal) else value
                for key, value in pricing.model_dump().items()
            }
            suggested_price = pricing.suggested_price_rub
            draft_variants: list[dict[str, Any]] = [
                {
                    "variant_id": variant.id,
                    "offer_id": variant.internal_sku,
                    "sku": variant.internal_sku,
                    "source_sku_id": variant.source_sku_id,
                    "name": variant.name,
                    "color": variant.color,
                    "size": variant.size,
                    "price": float(suggested_price),
                    "stock": variant.stock,
                    "image": variant.image,
                }
                for variant in product.variants
            ]
            draft = self.drafts.upsert_pending(
                product_id=product.id,
                ai_result=ai_result,
                title=output.title_ru,
                description=output.description_ru,
                category_id=category_id,
                attributes=attributes,
                variants=draft_variants,
                images=product.images,
                pricing=pricing_payload,
                price=suggested_price,
                stock=product.stock,
            )
            self.products.save_status(
                product,
                ai_status="completed",
                ozon_status="published" if has_published_draft else "review",
                estimated_price=suggested_price,
                estimated_profit_margin=pricing.estimated_profit_margin,
            )
            self.task_service.succeed(
                task,
                {"product_id": product.id, "ai_result_id": ai_result.id, "draft_id": draft.id, **processing_context},
            )
            self.logs.add(
                "INFO",
                "AI",
                "AI 商品加工及 Ozon 草稿生成成功",
                {"product_id": product.id, "ai_result_id": ai_result.id, "draft_id": draft.id, **processing_context},
            )
            return self.products.get(product.id), draft, task.id
        except Exception as exc:
            self.products.save_status(product, ai_status="failed")
            self.task_service.fail(task, exc)
            self.logs.add(
                "ERROR", "AI", "AI 商品加工失败", {"product_id": product.id, "error": str(exc), **processing_context}
            )
            raise

    def update_draft(self, draft_id: int, update: DraftUpdate) -> OzonDraft:
        draft = self.drafts.update(draft_id, update)
        margin = Decimal(str(draft.pricing.get("estimated_profit_margin", 0)))
        has_published_draft = any(
            item.status == "published" for item in draft.product.drafts
        )
        self.products.save_status(
            draft.product,
            ozon_status="published" if has_published_draft else "review",
            estimated_price=draft.price,
            estimated_profit_margin=margin,
        )
        self.logs.add("INFO", "Ozon", "Ozon 草稿已保存", {"draft_id": draft.id})
        return draft

    def publish(self, draft_id: int, *, confirmed: bool) -> tuple[OzonDraft, int]:
        if not confirmed:
            raise ConflictError("发布前必须由用户明确确认")
        draft = self.drafts.get(draft_id)
        if (
            source_data_kind(draft.product.source_product.source, draft.product.source_product.raw_payload) == "real"
            and isinstance(self.ozon_connector, MockOzonConnector)
        ):
            raise ConflictError("真实商品不能通过模拟接口发布。请先接入真实 Ozon API；没有向 Ozon 提交商品。")
        if draft.status == "published":
            raise ConflictError("该草稿已发布")
        if draft.status == "stale":
            raise ConflictError("源商品已发生变化，请重新进行 AI 加工后再发布草稿")
        self._validate_publishable_draft(draft)
        task = self.task_service.create("publish_ozon", {"draft_id": draft.id, "mock": True, "data_kind": "mock"})
        self.task_service.start(task, progress=10)
        try:
            payload = {
                "title": draft.title,
                "description": draft.description,
                "category_id": draft.category_id,
                "attributes": draft.attributes,
                "variants": draft.variants,
                "images": draft.images,
                "price": float(draft.price),
                "stock": draft.stock,
            }
            result = self.ozon_connector.publish_draft(draft.id, payload)
            draft.status = result.status
            draft.publication_id = result.publication_id
            draft.reviewed_at = utc_now()
            draft.published_at = utc_now()
            draft = self.drafts.save(draft)
            self.products.save_status(draft.product, ozon_status="published")
            self.task_service.succeed(
                task,
                {"draft_id": draft.id, "publication_id": result.publication_id, "mock": True, "data_kind": "mock"},
            )
            self.logs.add(
                "INFO",
                "Ozon",
                "Mock Ozon 发布成功",
                {"draft_id": draft.id, "publication_id": result.publication_id, "mock": True, "data_kind": "mock"},
            )
            return draft, task.id
        except Exception as exc:
            self.task_service.fail(task, exc)
            self.logs.add(
                "ERROR", "Ozon", "Ozon 发布失败", {"draft_id": draft.id, "error": str(exc), "mock": True, "data_kind": "mock"}
            )
            raise

    @staticmethod
    def _validate_publishable_draft(draft: OzonDraft) -> None:
        missing: list[str] = []
        if not draft.title.strip():
            missing.append("标题")
        if not draft.description.strip():
            missing.append("描述")
        if not draft.category_id.strip():
            missing.append("类目")
        if not draft.attributes:
            missing.append("属性")
        if not draft.images:
            missing.append("图片")
        if not draft.variants:
            missing.append("SKU")
        if missing:
            raise ValidationError(f"草稿缺少发布必填内容：{'、'.join(missing)}")

        variant_stock = sum(
            max(0, int(item.get("stock", 0))) for item in draft.variants
        )
        if variant_stock != draft.stock:
            raise ValidationError("草稿总库存与 SKU 库存之和不一致")

    @staticmethod
    def _ai_input(product: Product) -> dict[str, Any]:
        return {
            "product_id": product.id,
            "data_kind": source_data_kind(product.source_product.source, product.source_product.raw_payload),
            "data_provider": source_data_provider(product.source_product.source, product.source_product.raw_payload),
            "title_original": product.title_original,
            "description_original": product.description_original,
            "category_original": product.category_original,
            "attributes": product.attributes,
            "purchase_price": float(product.purchase_price),
            "currency": product.currency,
            "images": product.images,
            "weight_kg": float(product.weight_kg) if product.weight_kg else None,
            "dimensions_cm": product.dimensions_cm,
            "variants": [
                {
                    "source_sku_id": variant.source_sku_id,
                    "name": variant.name,
                    "color": variant.color,
                    "size": variant.size,
                    "purchase_price": float(variant.purchase_price),
                    "stock": variant.stock,
                }
                for variant in product.variants
            ],
        }

