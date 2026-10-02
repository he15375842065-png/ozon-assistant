from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field, model_validator


class PricingInput(BaseModel):
    purchase_price_cny: Decimal = Field(gt=0)
    domestic_logistics_cny: Decimal = Field(default=Decimal("8"), ge=0)
    international_logistics_cny: Decimal = Field(default=Decimal("24"), ge=0)
    other_costs_cny: Decimal = Field(default=Decimal("2"), ge=0)
    exchange_rate_rub_per_cny: Decimal = Field(default=Decimal("12.50"), gt=0)
    ozon_commission_rate: Decimal = Field(default=Decimal("0.16"), ge=0, lt=1)
    payment_platform_rate: Decimal = Field(default=Decimal("0.02"), ge=0, lt=1)
    advertising_rate: Decimal = Field(default=Decimal("0.08"), ge=0, lt=1)
    return_loss_rate: Decimal = Field(default=Decimal("0.04"), ge=0, lt=1)
    target_profit_margin: Decimal = Field(default=Decimal("0.25"), ge=0, lt=1)

    @model_validator(mode="after")
    def validate_rates(self) -> "PricingInput":
        variable_rate = (
            self.ozon_commission_rate
            + self.payment_platform_rate
            + self.advertising_rate
            + self.return_loss_rate
        )
        if variable_rate >= 1:
            raise ValueError("platform and risk rates must total less than 100%")
        if variable_rate + self.target_profit_margin >= 1:
            raise ValueError("rates plus target profit margin must total less than 100%")
        return self


class PricingResult(BaseModel):
    fixed_cost_cny: Decimal
    fixed_cost_rub: Decimal
    minimum_price_rub: Decimal
    suggested_price_rub: Decimal
    estimated_total_cost_rub: Decimal
    estimated_profit_rub: Decimal
    estimated_profit_margin: Decimal
    variable_cost_rate: Decimal
    target_profit_margin: Decimal


class PricingEngine:
    _MONEY = Decimal("0.01")

    def calculate(self, request: PricingInput) -> PricingResult:
        fixed_cny = (
            request.purchase_price_cny
            + request.domestic_logistics_cny
            + request.international_logistics_cny
            + request.other_costs_cny
        )
        fixed_rub = fixed_cny * request.exchange_rate_rub_per_cny
        variable_rate = (
            request.ozon_commission_rate
            + request.payment_platform_rate
            + request.advertising_rate
            + request.return_loss_rate
        )
        minimum_raw = fixed_rub / (Decimal("1") - variable_rate)
        suggested_raw = fixed_rub / (
            Decimal("1") - variable_rate - request.target_profit_margin
        )
        suggested = self._retail_round(suggested_raw)
        total_cost = fixed_rub + suggested * variable_rate
        profit = suggested - total_cost
        margin = profit / suggested
        return PricingResult(
            fixed_cost_cny=self._money(fixed_cny),
            fixed_cost_rub=self._money(fixed_rub),
            minimum_price_rub=self._money(minimum_raw),
            suggested_price_rub=self._money(suggested),
            estimated_total_cost_rub=self._money(total_cost),
            estimated_profit_rub=self._money(profit),
            estimated_profit_margin=margin.quantize(Decimal("0.0001"), ROUND_HALF_UP),
            variable_cost_rate=variable_rate.quantize(Decimal("0.0001"), ROUND_HALF_UP),
            target_profit_margin=request.target_profit_margin.quantize(
                Decimal("0.0001"), ROUND_HALF_UP
            ),
        )

    @classmethod
    def _money(cls, value: Decimal) -> Decimal:
        return value.quantize(cls._MONEY, ROUND_HALF_UP)

    @staticmethod
    def _retail_round(value: Decimal) -> Decimal:
        # Round up to a familiar x99 RUB price without dropping below the target.
        hundreds = ((value + Decimal("1")) / Decimal("100")).to_integral_value(
            rounding=ROUND_CEILING
        )
        return max(Decimal("99"), hundreds * Decimal("100") - Decimal("1"))
