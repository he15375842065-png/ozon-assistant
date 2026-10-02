"""Ozon Seller API HTTP client.

Covers the endpoints needed for V2: category metadata, product import,
price/stock updates and a lightweight connectivity check.

Authentication: ``Client-Id`` + ``Api-Key`` headers, per the official Seller
API. Base URL defaults to ``https://api-seller.ozon.ru`` (already reserved in
``.env.example`` as ``OZON_ASSISTANT_OZON_API_BASE_URL``).

Rate limiting (HTTP 429) and transient 5xx responses are retried with
exponential backoff. Credentials are never written to logs.
"""

from __future__ import annotations

import time
from typing import Any

import httpx


class OzonAPIError(RuntimeError):
    """Base error for Ozon Seller API failures."""


class OzonAuthError(OzonAPIError):
    """Credentials were rejected (HTTP 401/403)."""


class OzonRateLimitError(OzonAPIError):
    """Rate limited after retries (HTTP 429)."""


def _error_message(status_code: int, body: Any) -> str:
    if isinstance(body, dict):
        details = body.get("details") or body.get("error") or body.get("message")
        if isinstance(details, str) and details.strip():
            return details.strip()
        message = body.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return f"HTTP {status_code}"


class OzonSellerClient:
    """Thin authenticated wrapper around the Ozon Seller API."""

    def __init__(
        self,
        *,
        client_id: str,
        api_key: str,
        base_url: str = "https://api-seller.ozon.ru",
        timeout_s: float = 60.0,
        max_retries: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        if not client_id or not client_id.strip():
            raise ValueError("Ozon client_id 不能为空")
        if not api_key or not api_key.strip():
            raise ValueError("Ozon api_key 不能为空")
        self.base_url = (base_url or "https://api-seller.ozon.ru").rstrip("/")
        self._client_id = client_id.strip()
        self._api_key = api_key
        self.timeout_s = timeout_s
        self.max_retries = max(0, max_retries)
        self._client = client

    # -- low level ------------------------------------------------------

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {
            "Client-Id": self._client_id,
            "Api-Key": self._api_key,
            "Content-Type": "application/json",
        }

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(
            headers=self._auth_headers,
            timeout=self.timeout_s,
        )

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        """POST to the Seller API and return the ``result`` field."""
        client = self._http()
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.post(
                    url, json=payload, headers=self._auth_headers
                )
            except httpx.TimeoutException as exc:
                raise OzonAPIError(f"Ozon 请求超时（{self.timeout_s}s）。") from exc
            except httpx.HTTPError as exc:
                raise OzonAPIError(f"Ozon 请求网络失败：{exc}") from exc
            if response.status_code in (401, 403):
                raise OzonAuthError("Ozon Client-Id / Api-Key 无效（401/403）。")
            if response.status_code == 429:
                last_error = OzonRateLimitError("Ozon 接口限流（429），请稍后重试。")
            elif 500 <= response.status_code < 600:
                last_error = OzonAPIError(
                    f"Ozon 接口服务异常：{_error_message(response.status_code, _safe_json(response))}。"
                )
            elif 400 <= response.status_code < 500:
                raise OzonAPIError(
                    f"Ozon 请求被拒绝：{_error_message(response.status_code, _safe_json(response))}。"
                )
            else:
                body = _safe_json(response)
                if isinstance(body, dict) and "result" in body:
                    return body["result"]
                return body
            if attempt < self.max_retries:
                time.sleep(min(2**attempt, 10))
        assert last_error is not None
        raise last_error

    # -- catalog metadata -----------------------------------------------

    def category_tree(self, language: str = "ZH_HANS") -> list[dict[str, Any]]:
        """Return the full category tree (nested ``children`` lists)."""
        result = self.post("/v2/category/tree", {"language": language})
        return result if isinstance(result, list) else []

    def category_attributes(
        self, category_id: int, language: str = "ZH_HANS"
    ) -> list[dict[str, Any]]:
        """Return attribute definitions for one category."""
        result = self.post(
            "/v3/category/attribute",
            {"category_id": [category_id], "language": language},
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            items = result.get("result") or result.get("attributes") or []
            return items if isinstance(items, list) else []
        return []

    # -- products ---------------------------------------------------------

    def import_products(self, items: list[dict[str, Any]]) -> int:
        """Submit a product import; returns the async ``task_id``."""
        result = self.post("/v3/product/import", {"items": items})
        task_id = result.get("task_id") if isinstance(result, dict) else None
        if not isinstance(task_id, int):
            raise OzonAPIError("Ozon 未返回合法的 task_id。")
        return task_id

    def import_info(self, task_id: int) -> dict[str, Any]:
        """Poll the status of a product import task."""
        result = self.post("/v1/product/import/info", {"task_id": task_id})
        return result if isinstance(result, dict) else {}

    def product_list(
        self, *, limit: int = 10, last_id: str = "", visibility: str = "ALL"
    ) -> dict[str, Any]:
        result = self.post(
            "/v3/product/list",
            {"filter": {"visibility": visibility}, "limit": limit, "last_id": last_id},
        )
        return result if isinstance(result, dict) else {}

    def check_connection(self) -> dict[str, Any]:
        """Lightweight credential check: list a single product."""
        result = self.product_list(limit=1)
        items = result.get("items") if isinstance(result, dict) else None
        return {
            "ok": True,
            "items_returned": len(items) if isinstance(items, list) else 0,
        }

    # -- prices & stocks ----------------------------------------------------

    def import_prices(self, prices: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk price update. Each item: product_id/offer_id + price fields."""
        result = self.post("/v1/product/import/prices", {"prices": prices})
        return result if isinstance(result, dict) else {}

    def update_stocks(self, stocks: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk stock update. Each item: product_id/offer_id + stock + warehouse_id."""
        result = self.post("/v2/products/stocks", {"stocks": stocks})
        return result if isinstance(result, dict) else {}


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None
