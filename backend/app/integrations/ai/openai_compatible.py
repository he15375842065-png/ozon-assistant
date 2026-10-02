"""OpenAI-compatible chat-completions AI provider.

Works with any OpenAI-compatible ``/chat/completions`` endpoint, including
DeepSeek (``https://api.deepseek.com``). Structured product data is requested
as JSON and validated against :class:`AIProductOutput`, so the rest of the
pipeline keeps the same contract as the mock provider.

DeepSeek notes:
- ``deepseek-chat`` supports ``response_format: {"type": "json_object"}``.
- ``deepseek-reasoner`` does NOT support JSON mode; for models whose name
  contains ``reasoner`` the parameter is omitted and the reply is parsed
  defensively instead.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from app.integrations.ai.base import AIProductOutput, AIProvider


class AIProviderError(RuntimeError):
    """Base error for real AI provider failures."""


class AIProviderAuthError(AIProviderError):
    """Credentials were rejected by the AI endpoint (HTTP 401/403)."""


class AIProviderRateLimitError(AIProviderError):
    """The AI endpoint rate-limited the request after retries (HTTP 429)."""


class AIProviderResponseError(AIProviderError):
    """The AI endpoint returned data that could not be used."""


_SYSTEM_PROMPT = """你是 Ozon（俄罗斯电商平台）商品资料专家。用户给你一个 1688 商品的原始信息，
你需要生成可直接用于 Ozon 上架的俄语商品资料。

严格要求：
1. 只输出一个 JSON 对象，不要输出任何解释、前言或 markdown 包裹。
2. JSON 字段必须 exactly 如下（缺一不可，多余字段会被忽略）：
{
  "title_ru": "俄语标题，1-500字符，包含核心关键词，不堆砌",
  "description_ru": "俄语详情描述，分段，突出卖点、材质、尺寸、适用场景",
  "category_suggestion": "建议的 Ozon 类目中文名",
  "category_id_suggestion": "建议的 Ozon 类目 ID（字符串；不确定就填空字符串）",
  "category_confidence": 0.0到1.0的置信度数字",
  "attributes_suggestion": {"材质": "...", "风格": "...", "适用场景": "..."},
  "risk_level": "low/medium/high 其中之一",
  "risk_checks": [{"code": "检查项英文标识", "level": "low/medium/high", "message": "俄语说明"}]
}
3. risk_checks 必须包含 brand_claims（品牌/夸大宣传检查）和 restricted_goods（禁限售检查）。
4. 不要编造品牌名；原标题含品牌词时在 risk_checks 中标记。
5. 所有面向买家的文本使用俄语；category_suggestion 使用中文。
"""


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply, tolerating fences."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIProviderResponseError(
                "AI 返回的内容不是合法 JSON，已放弃解析。"
            ) from None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AIProviderResponseError(
                f"AI 返回的 JSON 解析失败：{exc}"
            ) from exc
    if not isinstance(data, dict):
        raise AIProviderResponseError("AI 返回的 JSON 不是对象，已放弃解析。")
    return data


class OpenAICompatibleAIProvider(AIProvider):
    """AI provider speaking the OpenAI ``/chat/completions`` protocol."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url or not base_url.strip():
            raise ValueError("AI base_url 不能为空")
        if not api_key or not api_key.strip():
            raise ValueError("AI api_key 不能为空")
        if not model or not model.strip():
            raise ValueError("AI model 不能为空")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.max_retries = max(0, max_retries)
        self._client = client
        self.last_token_usage: int | None = None

    # -- public API -----------------------------------------------------

    def generate_product(self, product: dict[str, Any]) -> AIProductOutput:
        payload = self._build_payload(product)
        data = self._post_with_retry("/chat/completions", payload)
        try:
            choices = data["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderResponseError(
                "AI 接口返回结构异常，缺少 choices/message/content。"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise AIProviderResponseError("AI 返回了空内容。")
        parsed = _extract_json_object(content)
        try:
            output = AIProductOutput.model_validate(parsed)
        except Exception as exc:  # pydantic ValidationError
            raise AIProviderResponseError(
                f"AI 返回的数据未通过结构校验：{exc}"
            ) from exc
        usage = data.get("usage") or {}
        total = usage.get("total_tokens")
        self.last_token_usage = int(total) if isinstance(total, int) else None
        return output

    def check_connection(self) -> dict[str, Any]:
        """Lightweight credential check against ``GET /models``."""
        try:
            response = self._client_or_new().get(
                f"{self.base_url}/models", timeout=self.timeout_s
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError(f"连接 AI 接口超时（{self.timeout_s}s）。") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"连接 AI 接口失败：{exc}") from exc
        if response.status_code in (401, 403):
            raise AIProviderAuthError("AI API Key 无效或无权限（401/403）。")
        if response.status_code == 404:
            # Some compatible gateways don't implement /models; treat the
            # endpoint as reachable but unverifiable.
            return {"ok": True, "verified": False, "models": []}
        if response.status_code >= 400:
            raise AIProviderError(
                f"AI 接口连接检查失败：HTTP {response.status_code}。"
            )
        models: list[str] = []
        try:
            body = response.json()
            for item in body.get("data", []):
                model_id = item.get("id")
                if isinstance(model_id, str):
                    models.append(model_id)
        except (ValueError, AttributeError):
            models = []
        return {"ok": True, "verified": True, "models": models}

    # -- internals ------------------------------------------------------

    def _client_or_new(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )

    def _build_payload(self, product: dict[str, Any]) -> dict[str, Any]:
        title = str(product.get("title") or product.get("name") or "")
        attributes = product.get("attributes") or {}
        variants = product.get("variants") or product.get("skus") or []
        images = product.get("images") or product.get("image_urls") or []
        user_content = (
            "商品原始信息（中文）：\n"
            f"标题：{title}\n"
            f"属性：{json.dumps(attributes, ensure_ascii=False)}\n"
            f"SKU（最多10个）：{json.dumps(variants[:10], ensure_ascii=False)}\n"
            f"图片数量：{len(images) if isinstance(images, list) else images}\n"
            "请按系统指令只输出 JSON 对象。"
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.temperature,
        }
        # deepseek-reasoner 不支持 response_format，必须省略。
        if "reasoner" not in self.model.lower():
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _post_with_retry(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        client = self._client_or_new()
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.post(url, json=payload, timeout=self.timeout_s)
            except httpx.TimeoutException as exc:
                last_error = AIProviderError(
                    f"AI 请求超时（{self.timeout_s}s），已重试 {attempt} 次。"
                )
                break
            except httpx.HTTPError as exc:
                last_error = AIProviderError(f"AI 请求网络失败：{exc}")
                break
            if response.status_code in (401, 403):
                raise AIProviderAuthError(
                    "AI API Key 无效或无权限（401/403），请检查配置。"
                )
            if response.status_code == 429:
                last_error = AIProviderRateLimitError(
                    "AI 接口限流（429），请稍后重试。"
                )
            elif 500 <= response.status_code < 600:
                last_error = AIProviderError(
                    f"AI 接口服务异常：HTTP {response.status_code}。"
                )
            elif 400 <= response.status_code < 500:
                raise AIProviderError(
                    f"AI 请求被拒绝：HTTP {response.status_code}。"
                )
            else:
                try:
                    data = response.json()
                except ValueError as exc:
                    raise AIProviderResponseError(
                        "AI 接口返回了非 JSON 响应。"
                    ) from exc
                if not isinstance(data, dict):
                    raise AIProviderResponseError("AI 接口返回结构异常。")
                return data
            if attempt < self.max_retries:
                time.sleep(2**attempt)
        assert last_error is not None
        raise last_error
