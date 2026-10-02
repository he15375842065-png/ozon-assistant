from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.common import ORMModel


class CollectProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    mode: Literal["real", "mock"] = "real"

    @field_validator("url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        from app.core.errors import ValidationError
        from app.integrations.sources.browser_1688 import validate_offer_url

        try:
            return HttpUrl(validate_offer_url(str(value)))
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc


class OpenSourceBrowserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl | None = None


class VariantRead(ORMModel):
    id: int
    source_sku_id: str
    internal_sku: str
    name: str
    color: str | None
    size: str | None
    purchase_price: float
    stock: int
    image: str | None


class AIResultRead(ORMModel):
    id: int
    provider: str
    model: str
    status: str
    title_ru: str
    description_ru: str
    category_suggestion: str
    category_id: str | None = None
    category_confidence: float
    attributes_suggestion: dict[str, Any]
    attributes: dict[str, Any]
    risk_level: str
    risk_checks: list[dict[str, Any]]
    risks: list[str]
    token_usage: int | None
    tokens: int | None
    latency_ms: int | None
    duration_ms: int | None
    error: str | None
    created_at: datetime


class ProductRead(BaseModel):
    id: int
    source_product_id: str
    source: str
    data_kind: Literal["mock", "real"]
    data_provider: str
    source_url: str
    title_original: str
    description_original: str
    category_original: str | None
    supplier: str | None
    purchase_price: float
    currency: str
    images: list[str]
    videos: list[str]
    attributes: dict[str, Any]
    variants: list[VariantRead]
    stock: int
    weight_kg: float | None
    dimensions_cm: dict[str, float]
    ai_status: str
    ozon_status: str
    estimated_price: float | None
    estimated_margin: float | None
    ai_result: AIResultRead | None = None
    draft_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int
    pages: int


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_original: str | None = Field(default=None, min_length=1, max_length=500)
    description_original: str | None = None
    category_original: str | None = Field(default=None, max_length=255)
    supplier: str | None = Field(default=None, max_length=255)
    purchase_price: float | None = Field(default=None, gt=0)
    images: list[str] | None = None
    attributes: dict[str, Any] | None = None
    stock: int | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, gt=0)
    dimensions_cm: dict[str, float] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_required_storage_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        required_fields = {
            "title_original",
            "description_original",
            "purchase_price",
            "images",
            "attributes",
            "stock",
            "dimensions_cm",
        }
        null_fields = sorted(
            field for field in required_fields if field in value and value[field] is None
        )
        if null_fields:
            raise ValueError(
                f"product fields cannot be null: {', '.join(null_fields)}"
            )
        return value

    @field_validator("images")
    @classmethod
    def validate_images(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        for image in value:
            parsed = urlparse(image)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError("image must be an absolute HTTP(S) URL")
        return value

    @field_validator("dimensions_cm")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is not None and any(dimension <= 0 for dimension in value.values()):
            raise ValueError("all dimensions must be greater than zero")
        return value


class WorkflowResponse(BaseModel):
    product: ProductRead
    task_id: int
    draft_id: int | None = None
    message: str
    collection_mode: Literal["real", "mock"]

