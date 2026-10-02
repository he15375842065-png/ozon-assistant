"""Real Ozon connector: publishes reviewed drafts via the Seller API.

Flow: build a ``/v3/product/import`` item from the reviewed draft, submit it,
then poll ``/v1/product/import/info`` until Ozon reports a terminal status.
Human confirmation is enforced by the caller (``workflow.publish``).

Attribute name→id resolution is delegated to an injected resolver with a
``resolve_attributes(category_id, attributes)`` method returning
``(resolved, unmapped, missing_required)`` tuples (see
``app.services.ozon_catalog.OzonCatalogService``). When no resolver is
available, attributes that already carry numeric ids pass through and the
rest are reported as unmapped instead of being silently dropped.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

from app.integrations.ozon.base import OzonConnector, OzonPublishResult
from app.integrations.ozon.client import OzonAPIError, OzonSellerClient


class AttributeResolver(Protocol):
    def resolve_attributes(
        self, category_id: int, attributes: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        ...


class RealOzonConnector(OzonConnector):
    name = "real"

    def __init__(
        self,
        client: OzonSellerClient,
        attribute_resolver: AttributeResolver | None = None,
        *,
        poll_interval_s: float = 5.0,
        poll_timeout_s: float = 180.0,
    ) -> None:
        self.client = client
        self.attribute_resolver = attribute_resolver
        self.poll_interval_s = poll_interval_s
        self.poll_timeout_s = poll_timeout_s

    # -- OzonConnector ----------------------------------------------------

    def publish_draft(self, draft_id: int, payload: dict[str, Any]) -> OzonPublishResult:
        item = self._build_item(draft_id, payload)
        warnings = item.pop("_warnings", [])
        task_id = self.client.import_products([item])
        product_id = self._await_import(task_id, item["offer_id"])
        return OzonPublishResult(
            publication_id=str(product_id),
            status="published",
            response={
                "mock": False,
                "task_id": task_id,
                "offer_id": item["offer_id"],
                "product_id": product_id,
                "warnings": warnings,
            },
        )

    # -- internals --------------------------------------------------------

    def _build_item(self, draft_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise OzonAPIError("草稿标题为空，无法发布。")
        try:
            category_id = int(str(payload.get("category_id") or "").strip())
        except ValueError as exc:
            raise OzonAPIError(
                "草稿类目 ID 不是有效的 Ozon 数字类目，请先同步类目并重新选择。"
            ) from exc
        weight_g = payload.get("weight_g")
        if not isinstance(weight_g, int) or weight_g <= 0:
            raise OzonAPIError("发布前请在草稿审核页填写商品重量（克）。")

        attributes = payload.get("attributes") or {}
        resolved, unmapped, missing_required = self._resolve_attributes(
            category_id, attributes if isinstance(attributes, dict) else {}
        )
        warnings: list[str] = []
        if unmapped:
            warnings.append(f"以下属性未匹配到 Ozon 属性 ID，已跳过：{', '.join(unmapped)}")
        if missing_required:
            warnings.append(
                f"类目必填属性缺失（可能导致 Ozon 拒收）：{', '.join(missing_required)}"
            )

        images, skipped_images = _public_image_urls(payload.get("images"))
        if skipped_images:
            warnings.append(
                f"{len(skipped_images)} 张图片不是公开 URL，已跳过（Ozon 只接受公开图片链接）。"
            )
        if not images:
            warnings.append("没有可用的公开图片链接；Ozon 要求至少一张图片，商品可能无法过审。")

        try:
            price = float(payload.get("price") or 0)
        except (TypeError, ValueError) as exc:
            raise OzonAPIError("草稿价格无效，无法发布。") from exc
        if price <= 0:
            raise OzonAPIError("草稿价格必须大于 0，无法发布。")

        item: dict[str, Any] = {
            "offer_id": f"OA-{draft_id}",
            "name": title[:255],
            "description": str(payload.get("description") or ""),
            "category_id": category_id,
            "price": f"{price:.2f}",
            "vat": "0",
            "weight": weight_g,
            "weight_unit": "g",
            "dimension_unit": "mm",
            "depth": _positive_int(payload.get("length_mm")),
            "width": _positive_int(payload.get("width_mm")),
            "height": _positive_int(payload.get("height_mm")),
            "images": images,
            "attributes": resolved,
        }
        # Drop dimension keys the user did not fill; Ozon treats 0 as invalid.
        for key in ("depth", "width", "height"):
            if not item[key]:
                del item[key]
        item["_warnings"] = warnings
        return item

    def _resolve_attributes(
        self, category_id: int, attributes: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        if self.attribute_resolver is not None:
            return self.attribute_resolver.resolve_attributes(category_id, attributes)
        resolved: list[dict[str, Any]] = []
        unmapped: list[str] = []
        for name, value in attributes.items():
            try:
                attribute_id = int(str(name).strip())
            except ValueError:
                unmapped.append(str(name))
                continue
            resolved.append(
                {"id": attribute_id, "values": [{"value": str(value).strip()}]}
            )
        return resolved, unmapped, []

    def _await_import(self, task_id: int, offer_id: str) -> int:
        deadline = time.monotonic() + self.poll_timeout_s
        while time.monotonic() < deadline:
            info = self.client.import_info(task_id)
            items = info.get("items") or []
            target = next(
                (i for i in items if str(i.get("offer_id")) == offer_id), None
            )
            if target is None:
                time.sleep(self.poll_interval_s)
                continue
            status = str(target.get("status") or "").lower()
            if status == "imported":
                product_id = target.get("product_id")
                if not isinstance(product_id, int):
                    raise OzonAPIError("Ozon 返回了异常的 product_id。")
                return product_id
            if status in ("failed", "rejected"):
                errors = target.get("errors") or []
                detail = "; ".join(
                    str(e.get("message") or e.get("code") or e)
                    for e in errors
                    if isinstance(e, dict)
                ) or "未知原因"
                raise OzonAPIError(f"Ozon 拒收该商品：{detail}")
            time.sleep(self.poll_interval_s)
        raise OzonAPIError(
            f"Ozon 导入超时（task_id={task_id}），商品可能仍在处理中，请稍后在卖家后台确认后再决定是否重试。"
        )


def _public_image_urls(images: Any) -> tuple[list[str], list[str]]:
    ok: list[str] = []
    skipped: list[str] = []
    if not isinstance(images, list):
        return ok, skipped
    for url in images:
        if isinstance(url, str) and url.strip().lower().startswith(("http://", "https://")):
            ok.append(url.strip())
        elif isinstance(url, str) and url.strip():
            skipped.append(url.strip())
    return ok, skipped


def _positive_int(value: Any) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0
