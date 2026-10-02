from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or ``backend/.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OZON_ASSISTANT_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Ozon Assistant API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/ozon_assistant.db"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "http://tauri.localhost",
            "tauri://localhost",
        ]
    )

    source_provider: Literal["browser", "mock"] = "browser"
    source_browser_profile: str = "./data/1688-browser-profile"
    source_browser_timeout_ms: int = Field(default=45000, ge=5000, le=180000)
    ai_provider: Literal["mock", "openai_compatible"] = "mock"
    ai_model: str = "mock-product-processor-v1"
    ai_temperature: float = 0.2
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_timeout_s: float = Field(default=60.0, ge=5, le=600)
    ai_max_retries: int = Field(default=2, ge=0, le=5)
    ozon_mode: Literal["mock", "real"] = "mock"
    ozon_client_id: str | None = None
    ozon_api_key: str | None = None
    ozon_api_base_url: str = "https://api-seller.ozon.ru"
    ozon_timeout_s: float = Field(default=60.0, ge=5, le=600)
    media_cache_dir: str = "./data/media"
    media_public_base_url: str | None = None

    pricing_exchange_rate: float = 12.5
    pricing_domestic_shipping: float = 8.0
    pricing_international_shipping: float = 24.0
    pricing_other_costs: float = 2.0
    pricing_platform_commission_rate: float = 0.16
    pricing_payment_fee_rate: float = 0.02
    pricing_advertising_rate: float = 0.08
    pricing_return_loss_rate: float = 0.04
    pricing_target_margin: float = 0.25


@lru_cache
def get_settings() -> Settings:
    return Settings()

