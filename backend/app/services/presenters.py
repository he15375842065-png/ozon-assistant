from app.models import AIResult, AppLog, OzonDraft, Product, Task
from app.schemas.drafts import DraftRead
from app.schemas.logs import LogRead
from app.schemas.products import AIResultRead, ProductRead, VariantRead
from app.schemas.tasks import TaskRead


def present_product(product: Product) -> ProductRead:
    latest_ai = product.latest_ai_result
    latest_draft = product.latest_draft
    return ProductRead(
        id=product.id,
        source_product_id=product.source_product.source_product_id,
        source=product.source_product.source,
        source_url=product.source_product.source_url,
        title_original=product.title_original,
        description_original=product.description_original,
        category_original=product.category_original,
        supplier=product.supplier,
        purchase_price=float(product.purchase_price),
        currency=product.currency,
        images=product.images,
        videos=product.videos,
        attributes=product.attributes,
        variants=[VariantRead.model_validate(variant) for variant in product.variants],
        stock=product.stock,
        weight_kg=float(product.weight_kg) if product.weight_kg is not None else None,
        dimensions_cm=product.dimensions_cm,
        ai_status=product.ai_status,
        ozon_status=product.ozon_status,
        estimated_price=(
            float(product.estimated_price) if product.estimated_price is not None else None
        ),
        estimated_margin=(
            round(float(product.estimated_profit_margin) * 100, 2)
            if product.estimated_profit_margin is not None
            else None
        ),
        ai_result=present_ai_result(latest_ai) if latest_ai else None,
        draft_id=latest_draft.id if latest_draft else None,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def present_draft(draft: OzonDraft) -> DraftRead:
    profit_margin = round(float(draft.pricing.get("estimated_profit_margin", 0)) * 100, 2)
    category_name = draft.ai_result.category_suggestion if draft.ai_result else None
    return DraftRead(
        id=draft.id,
        product_id=draft.product_id,
        title_ru=draft.title,
        description_ru=draft.description,
        category_id=draft.category_id,
        category_name=category_name,
        attributes=draft.attributes,
        images=draft.images,
        skus=draft.variants,
        status=draft.status,
        suggested_price=float(draft.price),
        profit_margin=profit_margin,
        pricing=draft.pricing,
        stock=draft.stock,
        publication_id=draft.publication_id,
        reviewed_at=draft.reviewed_at,
        published_at=draft.published_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def present_task(task: Task) -> TaskRead:
    return TaskRead(
        id=task.id,
        type=task.task_type,
        status=task.status,
        progress=task.progress,
        payload=task.payload,
        result=task.result,
        error=task.error,
        retries=task.retry_count,
        created_at=task.created_at,
        started_at=task.started_at,
        ended_at=task.finished_at,
    )


def present_ai_result(result: AIResult) -> AIResultRead:
    category_id = result.output_payload.get("category_id_suggestion")
    risks = [str(check.get("message", "")) for check in result.risk_checks if check.get("message")]
    return AIResultRead(
        id=result.id,
        provider=result.provider,
        model=result.model,
        status=result.status,
        title_ru=result.title_ru,
        description_ru=result.description_ru,
        category_suggestion=result.category_suggestion,
        category_id=str(category_id) if category_id is not None else None,
        category_confidence=float(result.category_confidence),
        attributes_suggestion=result.attributes_suggestion,
        attributes=result.attributes_suggestion,
        risk_level=result.risk_level,
        risk_checks=result.risk_checks,
        risks=risks,
        token_usage=result.token_usage,
        tokens=result.token_usage,
        latency_ms=result.latency_ms,
        duration_ms=result.latency_ms,
        error=result.error,
        created_at=result.created_at,
    )


def present_log(log: AppLog) -> LogRead:
    return LogRead(
        id=log.id,
        level=log.level,
        module=log.source,
        message=log.message,
        context=log.context,
        created_at=log.created_at,
    )

