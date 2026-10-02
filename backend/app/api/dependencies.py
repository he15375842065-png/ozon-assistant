from collections.abc import Generator
from decimal import Decimal
from typing import Literal

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import IntegrationError, ValidationError
from app.integrations.ai import (
    AIGateway,
    MockAIProvider,
    OpenAICompatibleAIProvider,
)
from app.integrations.ozon import (
    MockOzonConnector,
    OzonAttributeMapper,
    OzonCategoryMapper,
    OzonSellerClient,
    RealOzonConnector,
)
from app.integrations.sources import Alibaba1688Adapter, Mock1688Provider
from app.pricing import PricingEngine
from app.repositories import (
    DraftRepository,
    LogRepository,
    OzonCatalogRepository,
    ProductRepository,
    TaskRepository,
)
from app.services.workflow import ProductWorkflowService


def get_session(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.session()


def get_runtime_settings(request: Request) -> Settings:
    return request.app.state.settings


def pricing_options_from_settings(settings: Settings) -> dict[str, Decimal]:
    """Translate the mutable runtime settings into the pricing engine contract."""

    return {
        "domestic_logistics_cny": Decimal(str(settings.pricing_domestic_shipping)),
        "international_logistics_cny": Decimal(
            str(settings.pricing_international_shipping)
        ),
        "other_costs_cny": Decimal(str(settings.pricing_other_costs)),
        "exchange_rate_rub_per_cny": Decimal(str(settings.pricing_exchange_rate)),
        "ozon_commission_rate": Decimal(
            str(settings.pricing_platform_commission_rate)
        ),
        "payment_platform_rate": Decimal(str(settings.pricing_payment_fee_rate)),
        "advertising_rate": Decimal(str(settings.pricing_advertising_rate)),
        "return_loss_rate": Decimal(str(settings.pricing_return_loss_rate)),
        "target_profit_margin": Decimal(str(settings.pricing_target_margin)),
    }


def build_ai_gateway(settings: Settings) -> AIGateway:
    """Select the AI provider from runtime settings.

    Real providers require a base URL and API key; misconfiguration raises a
    clear error instead of silently falling back to the mock provider.
    """
    if settings.ai_provider == "openai_compatible":
        if not settings.ai_base_url or not settings.ai_api_key:
            raise IntegrationError(
                "真实 AI 需要配置 Base URL 和 API Key（设置页 AI Gateway）。"
            )
        provider = OpenAICompatibleAIProvider(
            base_url=settings.ai_base_url,
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            temperature=settings.ai_temperature,
            timeout_s=settings.ai_timeout_s,
            max_retries=settings.ai_max_retries,
        )
    else:
        provider = MockAIProvider(settings.ai_model)
    return AIGateway(provider)


def build_ozon_client(
    settings: Settings,
    *,
    client_id: str | None = None,
    api_key: str | None = None,
) -> OzonSellerClient:
    resolved_client_id = (client_id or settings.ozon_client_id or "").strip()
    if client_id is not None or api_key is not None:
        resolved_api_key = api_key or ""
    else:
        resolved_api_key = settings.ozon_api_key or ""
    if not resolved_client_id or not resolved_api_key:
        raise ValidationError("请先填写 Ozon Client-Id 和 Api-Key。")
    return OzonSellerClient(
        client_id=resolved_client_id,
        api_key=resolved_api_key,
        base_url=settings.ozon_api_base_url,
        timeout_s=settings.ozon_timeout_s,
    )


def build_ozon_connector(
    settings: Settings, catalog: OzonCatalogRepository
):
    """Select the Ozon connector from runtime settings.

    Real mode requires Client-Id + Api-Key; misconfiguration raises a clear
    error instead of silently publishing through the mock connector.
    """
    if settings.ozon_mode == "real":
        if not settings.ozon_client_id or not settings.ozon_api_key:
            raise ValidationError(
                "真实 Ozon 模式需要配置 Client-Id 和 Api-Key（设置页 Ozon API）。"
            )
        from app.services.ozon_catalog import OzonCatalogService

        client = OzonSellerClient(
            client_id=settings.ozon_client_id,
            api_key=settings.ozon_api_key,
            base_url=settings.ozon_api_base_url,
            timeout_s=settings.ozon_timeout_s,
        )
        # Service doubles as the attribute resolver for the real connector.
        resolver = OzonCatalogService(catalog)
        return RealOzonConnector(client, attribute_resolver=resolver)
    return MockOzonConnector()


def build_workflow(
    session: Session,
    settings: Settings,
    *,
    collection_mode: Literal["real", "mock"] | None = None,
) -> ProductWorkflowService:
    mode = collection_mode or ("mock" if settings.source_provider == "mock" else "real")
    if mode == "mock":
        source_provider = Mock1688Provider()
    else:
        from app.integrations.sources.browser_1688 import Browser1688Provider

        source_provider = Browser1688Provider(
            settings.source_browser_profile, settings.source_browser_timeout_ms
        )
    return ProductWorkflowService(
        products=ProductRepository(session),
        drafts=DraftRepository(session),
        tasks=TaskRepository(session),
        logs=LogRepository(session),
        source_adapter=Alibaba1688Adapter(source_provider),
        collection_mode=mode,
        ai_gateway=build_ai_gateway(settings),
        category_mapper=OzonCategoryMapper(),
        attribute_mapper=OzonAttributeMapper(),
        pricing_engine=PricingEngine(),
        pricing_options=pricing_options_from_settings(settings),
        ozon_connector=build_ozon_connector(settings, OzonCatalogRepository(session)),
    )

