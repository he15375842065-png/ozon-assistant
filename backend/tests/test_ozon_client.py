import json

import httpx
import pytest

from app.integrations.ozon.client import (
    OzonAPIError,
    OzonAuthError,
    OzonRateLimitError,
    OzonSellerClient,
)


def _transport(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def _client(handler, **kwargs) -> OzonSellerClient:
    return OzonSellerClient(
        client_id="1", api_key="secret", client=_transport(handler), **kwargs
    )


def test_check_connection_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/product/list"
        return _ok({"result": {"items": []}})

    result = _client(handler).check_connection()
    assert result["ok"] is True
    assert result["items_returned"] == 0


def test_check_connection_auth_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"code": "UNAUTHORIZED", "message": "bad key"}}
        )

    with pytest.raises(OzonAuthError):
        _client(handler).check_connection()


def test_rate_limit_retries_then_succeeds():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return _ok({"result": {"task_id": 42}})

    assert _client(handler).import_products([{"offer_id": "x"}]) == 42
    assert len(calls) == 2


def test_rate_limit_exhaustion_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "slow down"}})

    with pytest.raises(OzonRateLimitError):
        _client(handler, max_retries=1).category_tree()


def test_server_error_retries_then_succeeds():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(500, json={"error": {"message": "boom"}})
        return _ok(
            {
                "result": {
                    "items": [
                        {"offer_id": "x", "status": "imported", "product_id": 7}
                    ]
                }
            }
        )

    info = _client(handler).import_info(42)
    assert info["items"][0]["product_id"] == 7
    assert len(calls) == 3


def test_auth_headers_sent():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Client-Id"] == "777"
        assert request.headers["Api-Key"] == "s3cr3t"
        assert request.headers["Content-Type"] == "application/json"
        return _ok({"result": {}})

    client = OzonSellerClient(
        client_id="777", api_key="s3cr3t", client=_transport(handler)
    )
    client.category_tree()


def test_network_failure_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns down", request=request)

    with pytest.raises(OzonAPIError, match="网络"):
        _client(handler).category_tree()


def test_import_products_returns_task_id():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["items"][0]["offer_id"] == "sku-1"
        return _ok({"result": {"task_id": 9001}})

    assert _client(handler).import_products([{"offer_id": "sku-1"}]) == 9001


def test_category_attributes_post_body():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["category_id"] == [17034433]
        assert body["language"] == "RU"
        return _ok({"result": [{"id": 1, "name": "尺寸"}]})

    attrs = _client(handler).category_attributes(17034433, language="RU")
    assert attrs == [{"id": 1, "name": "尺寸"}]


def test_blank_credentials_rejected():
    with pytest.raises(ValueError):
        OzonSellerClient(client_id=" ", api_key="x")
    with pytest.raises(ValueError):
        OzonSellerClient(client_id="1", api_key="")
