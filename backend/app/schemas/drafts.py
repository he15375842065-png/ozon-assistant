from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_http_url(value: str, field_name: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")
    return value


class DraftRead(BaseModel):
    id: int
    product_id: int
    title_ru: str
    description_ru: str
    category_id: str
    category_name: str | None
    attributes: dict[str, Any]
    images: list[str]
    skus: list[dict[str, Any]]
    status: str
    suggested_price: float
    profit_margin: float
    pricing: dict[str, Any]
    stock: int
    publication_id: str | None
    reviewed_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DraftList(BaseModel):
    items: list[DraftRead]
    total: int


class DraftSkuUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    variant_id: int | None = Field(default=None, gt=0)
    offer_id: str = Field(min_length=1, max_length=120)
    sku: str = Field(min_length=1, max_length=120)
    source_sku_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    color: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=120)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    image: str | None = None

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_http_url(value, "image")


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_ru: str | None = Field(default=None, min_length=1, max_length=500)
    description_ru: str | None = Field(default=None, min_length=1)
    category_id: str | None = Field(default=None, min_length=1, max_length=120)
    attributes: dict[str, Any] | None = None
    images: list[str] | None = None
    skus: list[DraftSkuUpdate] | None = Field(default=None, min_length=1)
    suggested_price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: Any) -> Any:
        if isinstance(value, dict):
            null_fields = [field for field, item in value.items() if item is None]
            if null_fields:
                raise ValueError(
                    f"draft fields cannot be null: {', '.join(sorted(null_fields))}"
                )
        return value

    @field_validator("images")
    @classmethod
    def validate_images(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [_validate_http_url(item, "image") for item in value]

    @model_validator(mode="after")
    def validate_unique_skus(self) -> "DraftUpdate":
        if self.skus is None:
            return self
        for field in ("offer_id", "sku", "source_sku_id"):
            values = [getattr(item, field) for item in self.skus]
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {field} values are not allowed")
        return self


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool = False


class PublishResponse(BaseModel):
    draft: DraftRead
    task_id: int
    message: str

