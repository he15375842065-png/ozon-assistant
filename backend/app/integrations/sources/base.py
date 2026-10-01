from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


def _validate_asset_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("asset URLs must be absolute HTTP(S) URLs")
    return value


class NormalizedVariantData(BaseModel):
    source_sku_id: str
    name: str
    color: str | None = None
    size: str | None = None
    purchase_price: float = Field(gt=0)
    stock: int = Field(ge=0)
    image: str | None = None

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str | None) -> str | None:
        return _validate_asset_url(value) if value is not None else None


class NormalizedProductData(BaseModel):
    source: str
    source_product_id: str
    source_url: HttpUrl
    title_original: str
    description_original: str = ""
    category_original: str | None = None
    supplier: str | None = None
    purchase_price: float = Field(gt=0)
    currency: str = "CNY"
    images: list[str] = Field(default_factory=list)
    videos: list[str] = Field(default_factory=list)
    variants: list[NormalizedVariantData] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    stock: int = Field(ge=0)
    weight_kg: float | None = Field(default=None, gt=0)
    dimensions_cm: dict[str, float] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("images", "videos")
    @classmethod
    def validate_asset_urls(cls, value: list[str]) -> list[str]:
        return [_validate_asset_url(item) for item in value]

    @field_validator("dimensions_cm")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        if any(dimension <= 0 for dimension in value.values()):
            raise ValueError("all dimensions must be greater than zero")
        return value

    @model_validator(mode="after")
    def validate_unique_variant_ids(self) -> "NormalizedProductData":
        variant_ids = [variant.source_sku_id for variant in self.variants]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("source_sku_id values must be unique within a product")
        if self.variants and self.stock != sum(item.stock for item in self.variants):
            raise ValueError("product stock must equal the sum of variant stock")
        return self


class ProductSourceAdapter(ABC):
    @abstractmethod
    def collect(self, url: str) -> NormalizedProductData:
        """Collect a source product and normalize it into the internal contract."""

