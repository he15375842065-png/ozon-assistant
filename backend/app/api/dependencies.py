from collections.abc import Generator
from decimal import Decimal

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.ai import AIGateway, MockAIProvider
from app.integrations.ozon import (
    MockOzonConnector,
    OzonAttributeMapper,
    OzonCategoryMapper,
)
from app.integrations.sources import Alibaba1688Adapter, Mock1688Provider
from app.pricing import PricingEngine
from app.repositories import DraftRepository, LogRepository, ProductRepository, TaskRepository
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


def build_workflow(session: Session, settings: Settings) -> ProductWorkflowService:
    return ProductWorkflowService(
        products=ProductRepository(session),
        drafts=DraftRepository(session),
        tasks=TaskRepository(session),
        logs=LogRepository(session),
        source_adapter=Alibaba1688Adapter(Mock1688Provider()),
        ai_gateway=AIGateway(MockAIProvider(settings.ai_model)),
        category_mapper=OzonCategoryMapper(),
        attribute_mapper=OzonAttributeMapper(),
        pricing_engine=PricingEngine(),
        pricing_options=pricing_options_from_settings(settings),
        ozon_connector=MockOzonConnector(),
    )

