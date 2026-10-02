from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SettingsRead(BaseModel):
    source_provider: str
    source_browser_profile: str
    source_browser_timeout_ms: int
    source_browser_channel: str
    ai_provider: str
    ai_model: str
    ai_temperature: float
    ai_base_url: str | None
    ai_api_key_configured: bool
    ozon_mode: str
    ozon_client_id_configured: bool
    ozon_api_key_configured: bool
    database_backend: str
    exchange_rate: float
    domestic_shipping: float
    international_shipping: float
    ozon_commission_rate: float
    target_margin: float


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_provider: Literal["browser", "mock"] | None = None
    source_browser_channel: Literal["chrome", "msedge"] | None = None
    ai_provider: Literal["mock", "openai_compatible"] | None = None
    ai_model: str | None = Field(default=None, min_length=1, max_length=120)
    ai_temperature: float | None = Field(default=None, ge=0, le=2)
    ai_base_url: str | None = None
    ai_api_key: str | None = Field(default=None, min_length=1, repr=False)
    ozon_mode: Literal["mock", "real"] | None = None
    ozon_client_id: str | None = Field(default=None, max_length=120)
    ozon_api_key: str | None = Field(default=None, min_length=1, repr=False)
    exchange_rate: float | None = Field(default=None, gt=0)
    domestic_shipping: float | None = Field(default=None, ge=0)
    international_shipping: float | None = Field(default=None, ge=0)
    ozon_commission_rate: float | None = Field(default=None, ge=0, lt=100)
    target_margin: float | None = Field(default=None, ge=0, lt=100)

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_runtime_required_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        required_fields = {
            "source_provider",
            "ai_provider",
            "ai_model",
            "ai_temperature",
            "ozon_mode",
            "exchange_rate",
            "domestic_shipping",
            "international_shipping",
            "ozon_commission_rate",
            "target_margin",
        }
        null_fields = sorted(
            field for field in required_fields if field in value and value[field] is None
        )
        if null_fields:
            raise ValueError(
                f"settings fields cannot be null: {', '.join(null_fields)}"
            )
        return value

    @field_validator("ai_base_url")
    @classmethod
    def validate_ai_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("ai_base_url must be an absolute HTTP(S) URL")
        return value.rstrip("/")


class AICheckRequest(BaseModel):
    """Connection test for a real AI provider.

    Any field left empty falls back to the current runtime settings, so the
    user can test credentials before saving them.
    """

    model_config = ConfigDict(extra="forbid")

    base_url: str | None = None
    api_key: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        return value.rstrip("/")

