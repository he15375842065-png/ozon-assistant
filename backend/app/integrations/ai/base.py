from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    level: str
    message: str


class AIProductOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_ru: str = Field(min_length=1, max_length=500)
    description_ru: str = Field(min_length=1)
    category_suggestion: str
    category_id_suggestion: str
    category_confidence: float = Field(ge=0, le=1)
    attributes_suggestion: dict[str, Any]
    risk_level: str
    risk_checks: list[RiskCheck]


class AIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate_product(self, product: dict[str, Any]) -> AIProductOutput:
        """Return validated structured product output."""


class AIGeneration(BaseModel):
    provider: str
    model: str
    output: AIProductOutput
    latency_ms: int
    token_usage: int | None = None


class AIGateway:
    """Stable boundary for swappable structured-output AI providers."""

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def process_product(self, product: dict[str, Any]) -> AIGeneration:
        started = perf_counter()
        output = self.provider.generate_product(product)
        latency_ms = max(1, round((perf_counter() - started) * 1000))
        return AIGeneration(
            provider=self.provider.name,
            model=self.provider.model,
            output=output,
            latency_ms=latency_ms,
        )

