"""Tests for the OpenAI-compatible AI provider (incl. DeepSeek support)."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.integrations.ai import (
    AIGateway,
    AIProviderAuthError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    OpenAICompatibleAIProvider,
)


VALID_OUTPUT = {
    "title_ru": "Органайзер для косметики, настольный",
    "description_ru": "Практичный органайзер для косметики и мелочей.",
    "category_suggestion": "Органайзеры для хранения",
    "category_id_suggestion": "17028922",
    "category_confidence": 0.9,
    "attributes_suggestion": {"material": "пластик"},
    "risk_level": "low",
    "risk_checks": [
        {"code": "brand_claims", "level": "low", "message": "ok"},
        {"code": "restricted_goods", "level": "low", "message": "ok"},
    ],
}


def _client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(
        transport=transport,
        headers={"Authorization": "Bearer sk-test", "Content-Type": "application/json"},
    )


def _ok_response(request: httpx.Request) -> httpx.Response:
    body = {
        "choices": [
            {"message": {"content": json.dumps(VALID_OUTPUT, ensure_ascii=False)}}
        ],
        "usage": {"total_tokens": 321},
    }
    return httpx.Response(200, json=body)


def _provider(handler, **kwargs) -> OpenAICompatibleAIProvider:
    defaults = dict(
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model="deepseek-chat",
        client=_client(handler),
    )
    defaults.update(kwargs)
    return OpenAICompatibleAIProvider(**defaults)


def _product() -> dict:
    return {
        "title": "桌面化妆品收纳盒",
        "attributes": {"材质": "塑料"},
        "variants": [{"sku": "A", "price": 12.5, "stock": 100}],
        "images": ["https://example.com/1.jpg"],
    }


def test_generate_product_success_and_token_usage() -> None:
    provider = _provider(_ok_response)
    output = provider.generate_product(_product())

    assert output.title_ru.startswith("Органайзер")
    assert output.category_confidence == 0.9
    assert provider.last_token_usage == 321

    gateway = AIGateway(provider)
    generation = gateway.process_product(_product())
    assert generation.provider == "openai_compatible"
    assert generation.model == "deepseek-chat"
    assert generation.token_usage == 321
    assert generation.latency_ms >= 1


def test_generate_product_parses_markdown_fenced_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(VALID_OUTPUT, ensure_ascii=False)
                        + "\n```"
                    }
                }
            ],
            "usage": {},
        }
        return httpx.Response(200, json=body)

    provider = _provider(handler)
    output = provider.generate_product(_product())
    assert output.title_ru.startswith("Органайзер")


def test_reasoner_model_skips_response_format() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode())
        return _ok_response(request)

    provider = _provider(handler, model="deepseek-reasoner")
    provider.generate_product(_product())
    assert "response_format" not in seen["payload"]


def test_chat_model_requests_json_object_mode() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode())
        return _ok_response(request)

    provider = _provider(handler, model="deepseek-chat")
    provider.generate_product(_product())
    assert seen["payload"]["response_format"] == {"type": "json_object"}


def test_retry_on_429_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return _ok_response(request)

    provider = _provider(handler, max_retries=2)
    output = provider.generate_product(_product())
    assert calls["n"] == 2
    assert output.title_ru.startswith("Органайзер")


def test_rate_limit_error_after_retries_exhausted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    provider = _provider(handler, max_retries=1)
    with pytest.raises(AIProviderRateLimitError):
        provider.generate_product(_product())


def test_auth_error_on_401() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    provider = _provider(handler, max_retries=2)
    with pytest.raises(AIProviderAuthError):
        provider.generate_product(_product())


def test_response_error_on_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "not json at all"}}]}
        )

    provider = _provider(handler)
    with pytest.raises(AIProviderResponseError):
        provider.generate_product(_product())


def test_response_error_on_schema_violation() -> None:
    bad = dict(VALID_OUTPUT)
    bad["category_confidence"] = 2.5  # out of range

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(bad)}}]}
        )

    provider = _provider(handler)
    with pytest.raises(AIProviderResponseError):
        provider.generate_product(_product())


def test_constructor_rejects_missing_credentials() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleAIProvider(base_url="", api_key="sk-x", model="m")
    with pytest.raises(ValueError):
        OpenAICompatibleAIProvider(
            base_url="https://api.deepseek.com", api_key="  ", model="m"
        )


def test_check_connection_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/models"
        assert request.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(200, json={"data": [{"id": "deepseek-chat"}]})

    provider = _provider(handler)
    result = provider.check_connection()
    assert result["ok"] is True
    assert result["verified"] is True
    assert "deepseek-chat" in result["models"]


def test_check_connection_auth_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    provider = _provider(handler)
    with pytest.raises(AIProviderAuthError):
        provider.check_connection()


def test_settings_accept_openai_compatible_provider() -> None:
    settings = Settings(ai_provider="openai_compatible")
    assert settings.ai_provider == "openai_compatible"


def test_build_ai_gateway_requires_credentials() -> None:
    from app.api.dependencies import build_ai_gateway
    from app.core.errors import IntegrationError

    settings = Settings(ai_provider="openai_compatible")
    with pytest.raises(IntegrationError):
        build_ai_gateway(settings)


def test_build_ai_gateway_builds_real_provider() -> None:
    from app.api.dependencies import build_ai_gateway

    settings = Settings(
        ai_provider="openai_compatible",
        ai_base_url="https://api.deepseek.com",
        ai_api_key="sk-test",
        ai_model="deepseek-chat",
    )
    gateway = build_ai_gateway(settings)
    assert isinstance(gateway.provider, OpenAICompatibleAIProvider)
    assert gateway.provider.model == "deepseek-chat"


def test_build_ai_gateway_keeps_mock_default() -> None:
    from app.api.dependencies import build_ai_gateway
    from app.integrations.ai import MockAIProvider

    gateway = build_ai_gateway(Settings())
    assert isinstance(gateway.provider, MockAIProvider)


def test_check_endpoint_rejects_missing_credentials(client) -> None:
    response = client.post("/api/v1/settings/ai/check", json={})
    assert response.status_code == 422
    assert "Base URL" in response.json()["message"]


def test_check_endpoint_validates_base_url(client) -> None:
    response = client.post(
        "/api/v1/settings/ai/check",
        json={"base_url": "not-a-url", "api_key": "sk-x"},
    )
    assert response.status_code == 422
