from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.pricing import PricingEngine, PricingInput


def test_pricing_is_deterministic_and_hits_target_margin() -> None:
    request = PricingInput(
        purchase_price_cny=Decimal("38"),
        domestic_logistics_cny=Decimal("8"),
        international_logistics_cny=Decimal("24"),
        other_costs_cny=Decimal("2"),
        exchange_rate_rub_per_cny=Decimal("12.5"),
        ozon_commission_rate=Decimal("0.16"),
        payment_platform_rate=Decimal("0.02"),
        advertising_rate=Decimal("0.08"),
        return_loss_rate=Decimal("0.04"),
        target_profit_margin=Decimal("0.25"),
    )

    first = PricingEngine().calculate(request)
    second = PricingEngine().calculate(request)

    assert first == second
    assert first.fixed_cost_cny == Decimal("72.00")
    assert first.fixed_cost_rub == Decimal("900.00")
    assert first.minimum_price_rub == Decimal("1285.71")
    assert first.suggested_price_rub == Decimal("2099.00")
    assert first.estimated_profit_margin >= request.target_profit_margin
    assert first.estimated_profit_rub == Decimal("569.30")


def test_pricing_rejects_impossible_rate_configuration() -> None:
    with pytest.raises(ValidationError):
        PricingInput(
            purchase_price_cny=Decimal("10"),
            ozon_commission_rate=Decimal("0.50"),
            advertising_rate=Decimal("0.30"),
            payment_platform_rate=Decimal("0.10"),
            return_loss_rate=Decimal("0.05"),
            target_profit_margin=Decimal("0.10"),
        )

