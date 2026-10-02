from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    build_ozon_client,
    build_workflow,
    get_runtime_settings,
    get_session,
    pricing_options_from_settings,
)
from app.core.config import Settings
from app.core.errors import IntegrationError, ValidationError
from app.integrations.ai import (
    AIProviderAuthError,
    AIProviderError,
    OpenAICompatibleAIProvider,
)
from app.integrations.ozon import OzonAPIError, OzonAuthError, OzonSellerClient
from app.repositories import (
    DraftRepository,
    LogRepository,
    OzonCatalogRepository,
    ProductRepository,
    TaskRepository,
)
from app.schemas.ozon import (
    OzonCategoryAttributeRead,
    OzonCategoryRead,
    OzonCheckRequest,
)
from app.services.ozon_catalog import OzonCatalogService
from app.pricing import PricingInput
from app.repositories import DraftRepository, LogRepository, ProductRepository, TaskRepository
from app.schemas.dashboard import DashboardRead
from app.schemas.drafts import (
    DraftList,
    DraftRead,
    DraftUpdate,
    PublishRequest,
    PublishResponse,
)
from app.schemas.logs import LogList
from app.schemas.products import (
    CollectProductRequest,
    OpenSourceBrowserRequest,
    ProductList,
    ProductRead,
    ProductUpdate,
    WorkflowResponse,
)
from app.schemas.settings import AICheckRequest, SettingsRead, SettingsUpdate
from app.schemas.tasks import TaskList, TaskRead
from app.services.dashboard import DashboardService
from app.services.presenters import present_draft, present_log, present_product, present_task
from app.services.tasks import TaskService
from app.integrations.sources.provenance import source_data_kind


router = APIRouter()


@router.get("/health", tags=["system"])
def health(settings: Settings = Depends(get_runtime_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "source_provider": settings.source_provider,
        "ai_provider": settings.ai_provider,
        "ozon_mode": settings.ozon_mode,
    }


@router.get("/dashboard", response_model=DashboardRead, tags=["dashboard"])
def dashboard(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_runtime_settings),
) -> DashboardRead:
    service = DashboardService(
        ProductRepository(session),
        TaskRepository(session),
        LogRepository(session),
        provider_status={
            "database": "connected",
            "source": settings.source_provider,
            "ai": settings.ai_provider,
            "ozon": settings.ozon_mode,
        },
    )
    return service.get()


@router.post(
    "/products/collect",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
)
def collect_product(
    request: CollectProductRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_runtime_settings),
) -> WorkflowResponse:
    product, task_id = build_workflow(session, settings, collection_mode=request.mode).collect(str(request.url))
    return WorkflowResponse(
        product=present_product(product),
        task_id=task_id,
        message="真实商品采集完成" if request.mode == "real" else "模拟样例采集完成（不是链接中的真实商品）",
        collection_mode=request.mode,
    )


@router.post("/sources/1688/browser/open", tags=["sources"])
def open_source_browser(
    request: OpenSourceBrowserRequest,
    settings: Settings = Depends(get_runtime_settings),
) -> dict[str, object]:
    from app.integrations.sources.browser_1688 import get_browser_manager

    return get_browser_manager(settings).open_browser(str(request.url) if request.url else None)


@router.get("/sources/1688/browser/status", tags=["sources"])
def source_browser_status(settings: Settings = Depends(get_runtime_settings)) -> dict[str, object]:
    from app.integrations.sources.browser_1688 import get_browser_manager

    return get_browser_manager(settings).status()


@router.get("/products", response_model=ProductList, tags=["products"])
def list_products(
    search: str | None = Query(default=None, max_length=200),
    ai_status: str | None = None,
    ozon_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ProductList:
    items, total, pages = ProductRepository(session).list(
        search=search,
        ai_status=ai_status,
        ozon_status=ozon_status,
        page=page,
        page_size=page_size,
    )
    return ProductList(
        items=[present_product(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/products/{product_id}", response_model=ProductRead, tags=["products"])
def get_product(
    product_id: int, session: Session = Depends(get_session)
) -> ProductRead:
    return present_product(ProductRepository(session).get(product_id))


@router.patch("/products/{product_id}", response_model=ProductRead, tags=["products"])
def update_product(
    product_id: int,
    update: ProductUpdate,
    session: Session = Depends(get_session),
) -> ProductRead:
    return present_product(ProductRepository(session).update(product_id, update))


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["products"],
)
def delete_product(product_id: int, session: Session = Depends(get_session)) -> Response:
    ProductRepository(session).delete(product_id)
    LogRepository(session).add("INFO", "database", "商品已删除", {"product_id": product_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/products/{product_id}/process",
    response_model=WorkflowResponse,
    tags=["products", "ai"],
)
def process_product(
    product_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_runtime_settings),
) -> WorkflowResponse:
    product, draft, task_id = build_workflow(session, settings).process(product_id)
    return WorkflowResponse(
        product=present_product(product),
        task_id=task_id,
        draft_id=draft.id,
        message="AI 加工、定价和 Ozon 草稿生成完成",
        collection_mode=source_data_kind(product.source_product.source, product.source_product.raw_payload),
    )


@router.get("/drafts", response_model=DraftList, tags=["drafts"])
def list_drafts(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> DraftList:
    items, total = DraftRepository(session).list(status_filter, limit)
    return DraftList(items=[present_draft(item) for item in items], total=total)


@router.get("/drafts/{draft_id}", response_model=DraftRead, tags=["drafts"])
def get_draft(draft_id: int, session: Session = Depends(get_session)) -> DraftRead:
    return present_draft(DraftRepository(session).get(draft_id))


@router.patch("/drafts/{draft_id}", response_model=DraftRead, tags=["drafts"])
def update_draft(
    draft_id: int,
    update: DraftUpdate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_runtime_settings),
) -> DraftRead:
    return present_draft(build_workflow(session, settings).update_draft(draft_id, update))


@router.post("/drafts/{draft_id}/publish", response_model=PublishResponse, tags=["drafts"])
def publish_draft(
    draft_id: int,
    request: PublishRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_runtime_settings),
) -> PublishResponse:
    draft, task_id = build_workflow(session, settings).publish(
        draft_id, confirmed=request.confirmed
    )
    return PublishResponse(
        draft=present_draft(draft),
        task_id=task_id,
        message="Mock Ozon 发布完成",
    )


@router.get("/tasks", response_model=TaskList, tags=["tasks"])
def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    task_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> TaskList:
    tasks, total = TaskRepository(session).list(
        status=status_filter, task_type=task_type, limit=limit
    )
    return TaskList(items=[present_task(task) for task in tasks], total=total)


@router.get("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def get_task(task_id: int, session: Session = Depends(get_session)) -> TaskRead:
    return present_task(TaskRepository(session).get(task_id))


@router.post("/tasks/{task_id}/cancel", response_model=TaskRead, tags=["tasks"])
def cancel_task(task_id: int, session: Session = Depends(get_session)) -> TaskRead:
    return present_task(TaskService(TaskRepository(session)).cancel(task_id))


@router.get("/logs", response_model=LogList, tags=["logs"])
def list_logs(
    level: str | None = None,
    module: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> LogList:
    logs, total = LogRepository(session).list(level=level, source=module, limit=limit)
    return LogList(items=[present_log(log) for log in logs], total=total)


def _settings_read(settings: Settings) -> SettingsRead:
    return SettingsRead(
        source_provider=settings.source_provider,
        source_browser_profile=settings.source_browser_profile,
        source_browser_timeout_ms=settings.source_browser_timeout_ms,
        source_browser_channel=settings.source_browser_channel,
        ai_provider=settings.ai_provider,
        ai_model=settings.ai_model,
        ai_temperature=settings.ai_temperature,
        ai_base_url=settings.ai_base_url,
        ai_api_key_configured=bool(settings.ai_api_key),
        ozon_mode=settings.ozon_mode,
        ozon_client_id_configured=bool(settings.ozon_client_id),
        ozon_api_key_configured=bool(settings.ozon_api_key),
        database_backend="sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
        exchange_rate=settings.pricing_exchange_rate,
        domestic_shipping=settings.pricing_domestic_shipping,
        international_shipping=settings.pricing_international_shipping,
        ozon_commission_rate=settings.pricing_platform_commission_rate * 100,
        target_margin=settings.pricing_target_margin * 100,
    )


@router.get("/settings", response_model=SettingsRead, tags=["settings"])
def read_settings(settings: Settings = Depends(get_runtime_settings)) -> SettingsRead:
    return _settings_read(settings)


@router.patch("/settings", response_model=SettingsRead, tags=["settings"])
def update_settings(
    update: SettingsUpdate,
    settings: Settings = Depends(get_runtime_settings),
) -> SettingsRead:
    changes = update.model_dump(exclude_unset=True)
    pricing_fields = {
        "exchange_rate": ("pricing_exchange_rate", 1),
        "domestic_shipping": ("pricing_domestic_shipping", 1),
        "international_shipping": ("pricing_international_shipping", 1),
        "ozon_commission_rate": ("pricing_platform_commission_rate", 100),
        "target_margin": ("pricing_target_margin", 100),
    }
    normalized_changes: dict[str, object] = {}
    for field, value in changes.items():
        if field in pricing_fields:
            target, divisor = pricing_fields[field]
            normalized_changes[target] = value / divisor
        else:
            normalized_changes[field] = value

    candidate = settings.model_copy(update=normalized_changes)
    try:
        PricingInput(
            purchase_price_cny=Decimal("1"),
            **pricing_options_from_settings(candidate),
        )
    except PydanticValidationError as exc:
        message = exc.errors()[0].get("msg", "invalid pricing configuration")
        raise ValidationError(f"定价设置无效：{message}") from exc

    for field, value in normalized_changes.items():
        setattr(settings, field, value)
    return _settings_read(settings)


@router.post("/settings/ai/check", tags=["settings"])
def check_ai_connection(
    request: AICheckRequest,
    settings: Settings = Depends(get_runtime_settings),
) -> dict[str, object]:
    """Test connectivity and credentials of the real AI provider.

    Empty fields fall back to the current runtime settings. The API key is
    never returned in the response.
    """
    base_url = (request.base_url or settings.ai_base_url or "").strip()
    api_key = request.api_key or settings.ai_api_key or ""
    model = (request.model or settings.ai_model or "").strip()
    if not base_url or not api_key:
        raise ValidationError("请先填写 Base URL 和 API Key，再测试连接。")
    provider = OpenAICompatibleAIProvider(
        base_url=base_url,
        api_key=api_key,
        model=model or "deepseek-chat",
        timeout_s=min(settings.ai_timeout_s, 30.0),
        max_retries=0,
    )
    try:
        result = provider.check_connection()
    except AIProviderAuthError as exc:
        raise ValidationError(str(exc)) from exc
    except AIProviderError as exc:
        raise IntegrationError(str(exc)) from exc
    return {"ok": True, "base_url": base_url, "model": provider.model, **result}


@router.post("/settings/ozon/check", tags=["settings"])
def check_ozon_connection(
    request: OzonCheckRequest,
    settings: Settings = Depends(get_runtime_settings),
) -> dict[str, object]:
    """Test connectivity and credentials of the Ozon Seller API.

    Empty fields fall back to the current runtime settings. Credentials are
    never returned in the response.
    """
    client = build_ozon_client(
        settings, client_id=request.client_id, api_key=request.api_key
    )
    try:
        result = client.check_connection()
    except OzonAuthError as exc:
        raise ValidationError(str(exc)) from exc
    except OzonAPIError as exc:
        raise IntegrationError(str(exc)) from exc
    return {"ok": True, **result}


def _ozon_catalog_service(
    session: Session, settings: Settings
) -> tuple[OzonSellerClient, OzonCatalogService]:
    client = build_ozon_client(settings)
    service = OzonCatalogService(
        OzonCatalogRepository(session), LogRepository(session)
    )
    return client, service


@router.post("/ozon/categories/sync", tags=["ozon"])
def sync_ozon_categories(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_runtime_settings),
) -> dict[str, object]:
    """Sync the full Ozon category tree into the local cache."""
    client, service = _ozon_catalog_service(session, settings)
    try:
        result = service.sync_tree(client)
    except OzonAuthError as exc:
        raise ValidationError(str(exc)) from exc
    except OzonAPIError as exc:
        raise IntegrationError(str(exc)) from exc
    session.commit()
    return result


@router.get("/ozon/categories", tags=["ozon"])
def search_ozon_categories(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[OzonCategoryRead]:
    """Search the locally cached Ozon category tree."""
    catalog = OzonCatalogRepository(session)
    return [
        OzonCategoryRead(
            category_id=item.category_id,
            name=item.name,
            parent_category_id=item.parent_category_id,
            level=item.level,
        )
        for item in catalog.search_categories(q, limit=limit)
    ]


@router.post(
    "/ozon/categories/{category_id}/attributes/sync", tags=["ozon"]
)
def sync_ozon_category_attributes(
    category_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_runtime_settings),
) -> dict[str, object]:
    """Sync attribute definitions for one Ozon category."""
    client, service = _ozon_catalog_service(session, settings)
    try:
        result = service.sync_attributes(client, category_id)
    except OzonAuthError as exc:
        raise ValidationError(str(exc)) from exc
    except OzonAPIError as exc:
        raise IntegrationError(str(exc)) from exc
    session.commit()
    return result


@router.get(
    "/ozon/categories/{category_id}/attributes", tags=["ozon"]
)
def get_ozon_category_attributes(
    category_id: int,
    session: Session = Depends(get_session),
) -> list[OzonCategoryAttributeRead]:
    """List cached attribute definitions for one Ozon category."""
    catalog = OzonCatalogRepository(session)
    return [
        OzonCategoryAttributeRead(
            attribute_id=item.attribute_id,
            name=item.name,
            is_required=item.is_required,
            attribute_type=item.attribute_type,
            dictionary_size=len(item.dictionary_values or []),
        )
        for item in catalog.get_attributes(category_id)
    ]


@router.get("/capabilities", response_model=dict[str, object], tags=["system"])
@router.get("/features", response_model=dict[str, object], tags=["system"])
def capabilities() -> dict[str, object]:
    return {
        "implemented": [
            "1688_mock_collection",
            "1688_browser_collection",
            "1688_browser_login",
            "collection_data_provenance",
            "product_library",
            "mock_ai_processing",
            "real_ai_processing",
            "ozon_mapping",
            "deterministic_pricing",
            "draft_review",
            "mock_publish",
            "task_center",
            "logs",
        ],
        "planned": [
            "real_ozon_connector",
            "inventory_sync",
            "order_management",
        ],
        "limitations": {
            "1688_browser_collection": "需用户在专用浏览器完成登录；验证码、访问限制或字段不完整会报错，不会使用模拟商品填充。",
            "ai_processing": "真实 AI（OpenAI Compatible，含 DeepSeek）已接入；使用 mock 时禁止用于真实商品。",
            "ozon_publish": "当前仅模拟发布；没有真实 Ozon 发布能力。",
        },
    }

