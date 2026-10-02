"""Parse observed 1688 page data without generating missing product facts.

This module does not fetch pages, run JavaScript, or bypass access controls. Its
inputs are browser observations. Supported shapes are intentionally conservative;
an unrecognized page fails instead of returning a demonstration product.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from app.core.errors import IntegrationError


_OFFER_PATH = re.compile(r"^/offer/(\d+)(?:\.html)?/?$", re.IGNORECASE)
_OFFER_KEYS = ("offerId", "offer_id", "productId", "product_id", "itemId")
_TITLE_KEYS = ("subject", "offerTitle", "title", "productTitle")
_SKU_KEYS = ("skuInfos", "skuList", "skuMap", "skus")
_SKIP_KEYS = re.compile(r"recommend|relatedOffer|advert|crossSell", re.IGNORECASE)
_PRODUCT_CONTAINERS = (
    "baseInfo", "offerInfo", "offerDetail", "productInfo", "currentProduct",
    "detail", "detailInfo", "skuModel", "skuInfo", "skuData", "saleInfo",
    "image", "imageInfo", "media", "shippingInfo", "supplier", "seller", "company",
)
_ASSIGNMENT = re.compile(
    r"(?<![\w$])(?:window\.)?(?:__INIT_DATA|__INITIAL_STATE__|__GLOBAL_DATA|"
    r"__GLOBAL_DATA__|iDetailData|offerData|__NEXT_DATA__|__PRELOADED_STATE__)\s*=\s*"
)


class _PageHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self.meta_image: str | None = None
        self._script: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script":
            self._script = []
        elif tag == "meta" and values.get("property") == "og:image":
            self.meta_image = values.get("content")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script is not None:
            self.scripts.append("".join(self._script))
            self._script = None

    def handle_data(self, data: str) -> None:
        if self._script is not None:
            self._script.append(data)


def _id(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    return text if text.isdigit() else None


def _offer_id(item: dict[str, Any]) -> str | None:
    for key in _OFFER_KEYS:
        if key in item and (value := _id(item[key])):
            return value
    # A generic id is only a product id when accompanied by a product title.
    if any(key in item for key in _TITLE_KEYS):
        return _id(item.get("id"))
    return None


def _walk(
    value: Any,
    expected_id: str,
    ancestors: tuple[dict[str, Any], ...] = (),
    depth: int = 0,
) -> Iterator[tuple[dict[str, Any], tuple[dict[str, Any], ...]]]:
    if depth > 20:
        return
    if isinstance(value, dict):
        own_id = _offer_id(value)
        if own_id is not None and own_id != expected_id:
            return
        yield value, ancestors
        for key, child in value.items():
            if not _SKIP_KEYS.search(str(key)):
                yield from _walk(child, expected_id, (*ancestors, value), depth + 1)
    elif isinstance(value, list):
        for child in value[:2000]:
            yield from _walk(child, expected_id, ancestors, depth + 1)


def _find(scope: dict[str, Any], keys: tuple[str, ...], expected_id: str, depth: int = 0) -> Any:
    """Read only known product sections inside one identity-bearing object.

    A generic recursive search could combine this offer's title with an unrelated
    carousel's SKU. Unknown sections are deliberately unsupported.
    """
    if depth > 20:
        return None
    own_id = _offer_id(scope)
    if own_id is not None and own_id != expected_id:
        return None
    for key in keys:
        value = scope.get(key)
        if value is not None and value != "" and value != [] and value != {}:
            return value
    for key in _PRODUCT_CONTAINERS:
        child = scope.get(key)
        if isinstance(child, dict):
            value = _find(child, keys, expected_id, depth + 1)
            if value is not None:
                return value
    return None


def _decode_json(text: str) -> list[Any]:
    text = text.strip()
    result: list[Any] = []
    try:
        result.append(json.loads(text))
    except (ValueError, TypeError):
        pass
    decoder = json.JSONDecoder()
    for match in _ASSIGNMENT.finditer(text):
        try:
            value, _ = decoder.raw_decode(text[match.end():].lstrip())
            result.append(value)
        except ValueError:
            continue
    # Deliberately do not eval JavaScript or parse arbitrary object literals.
    return result


def _number(value: Any, label: str, *, stock: bool = False) -> int | float:
    if isinstance(value, bool) or value is None:
        raise IntegrationError(f"真实 1688 数据缺少有效{label}，未保存商品")
    if isinstance(value, str):
        value = value.strip().removeprefix("¥").removeprefix("￥").strip()
        if not re.fullmatch(r"\d+(?:\.\d+)?", value):
            raise IntegrationError(f"真实 1688 {label}不是明确数值，未保存商品")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise IntegrationError(f"真实 1688 数据缺少有效{label}，未保存商品") from exc
    if not math.isfinite(number) or number < 0 or (not stock and number == 0):
        raise IntegrationError(f"真实 1688 {label}数值无效，未保存商品")
    if stock:
        if not number.is_integer():
            raise IntegrationError("真实 1688 SKU 库存不是整数，未保存商品")
        return int(number)
    return number


def _first(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item and item[key] is not None and item[key] != "":
            return item[key]
    return None


def _asset(value: Any) -> str | None:
    if isinstance(value, dict):
        value = _first(value, ("url", "imageUrl", "fullPath", "bigImage", "original"))
    if not isinstance(value, str):
        return None
    value = unescape(value.strip())
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
        return value
    return None


def _assets(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return list(dict.fromkeys(url for item in values if (url := _asset(item))))


def _attributes(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            key = _first(item, ("attributeDisplayName", "attributeName", "name", "key"))
            content = _first(item, ("attributeValue", "value", "valueName"))
            if isinstance(key, str) and content is not None:
                result[key] = content
    return result


def _tier_price(value: Any) -> Any:
    if not isinstance(value, list) or not value:
        return None
    tiers = [item for item in value if isinstance(item, dict) and "price" in item]
    if not tiers:
        return None
    # Use the first quantity tier, rather than a low bulk price that may not apply.
    def start(item: dict[str, Any]) -> float:
        try:
            return float(item.get("startQuantity", item.get("begin", 0)))
        except (TypeError, ValueError):
            return math.inf
    return min(tiers, key=start).get("price")


def _parse_candidate(
    scope: dict[str, Any], anchor: dict[str, Any], expected_id: str, source_url: str,
    page: _PageHTML,
) -> dict[str, Any]:
    title = _first(anchor, _TITLE_KEYS) or _find(anchor, _TITLE_KEYS, expected_id)
    if not isinstance(title, str) or not title.strip():
        raise IntegrationError("未读取到真实 1688 商品标题，未保存商品")
    images = _assets(_find(scope, ("images", "imageUrls", "imageList", "imageUrlList"), expected_id))
    if not images:
        images = _assets(_find(scope, ("imageUrl", "mainImage", "mainImageUrl"), expected_id))
    if not images:
        images = _assets(page.meta_image)
    if not images:
        raise IntegrationError("未读取到真实 1688 商品图片，未保存商品")

    sku_data = _find(scope, _SKU_KEYS, expected_id)
    if isinstance(sku_data, dict):
        sku_items = [(str(key), value) for key, value in sku_data.items()]
    elif isinstance(sku_data, list):
        sku_items = [(None, value) for value in sku_data]
    else:
        raise IntegrationError("未读取到真实 1688 SKU 数据，请确认来源页已加载完整；未保存商品")
    if not sku_items:
        raise IntegrationError("真实 1688 商品没有可读取的 SKU，未保存商品")

    skus: list[dict[str, Any]] = []
    for map_name, item in sku_items:
        if not isinstance(item, dict):
            raise IntegrationError("真实 1688 SKU 格式无法识别，未保存商品")
        sku_id = _first(item, ("skuId", "sku_id", "specId", "source_sku_id", "id"))
        if sku_id is None or isinstance(sku_id, bool) or not str(sku_id).strip():
            raise IntegrationError("真实 1688 SKU 缺少来源编号，未保存商品")
        properties = _attributes(item.get("attributes", item.get("props", {})))
        name = _first(item, ("name", "skuName", "specName"))
        if not name and properties:
            name = " / ".join(str(value) for value in properties.values())
        if not name:
            name = map_name
        if not isinstance(name, str) or not name.strip():
            raise IntegrationError("真实 1688 SKU 缺少规格名称，未保存商品")
        price = _first(item, ("price", "skuPrice", "salePrice"))
        if price is None:
            price = _tier_price(item.get("priceRanges"))
        stock = _first(item, ("amountOnSale", "stock", "inventory", "canBookCount"))
        skus.append({
            "sku_id": str(sku_id),
            "name": name.strip(),
            "color": _first(item, ("color", "colorName")) or _first(properties, ("颜色", "颜色分类", "color")),
            "size": _first(item, ("size", "sizeName")) or _first(properties, ("尺码", "尺寸", "size")),
            "price": _number(price, "SKU 采购价格"),
            "stock": _number(stock, "SKU 可售库存", stock=True),
            "image": _asset(_first(item, ("image", "imageUrl", "skuImageUrl"))),
        })
    if len({item["sku_id"] for item in skus}) != len(skus):
        raise IntegrationError("真实 1688 SKU 来源编号重复，未保存商品")

    description = _find(scope, ("description", "descriptionText", "detailDescription"), expected_id)
    description = unescape(re.sub(r"<[^>]*>", " ", description)).strip() if isinstance(description, str) else ""
    supplier = _first(anchor, ("supplier",))
    if not isinstance(supplier, str):
        supplier = _find(scope, ("companyName", "supplierName", "sellerName"), expected_id)
    if not isinstance(supplier, str):
        supplier = None
    category = _find(scope, ("categoryName", "categoryPath", "category"), expected_id)
    if not isinstance(category, str):
        category = None
    weight = _find(scope, ("unitWeight", "weight_kg"), expected_id)
    dimensions = _find(scope, ("dimensions_cm",), expected_id)
    return {
        "offer_id": expected_id,
        "url": source_url,
        "title": title.strip(),
        "description": description,
        "category": category,
        "supplier": supplier,
        "currency": "CNY",
        "images": images,
        "videos": _assets(_find(scope, ("videos", "videoUrls", "videoUrl"), expected_id)),
        "attributes": _attributes(_find(anchor, ("attributes", "productAttributes", "props"), expected_id)),
        "weight_kg": _number(weight, "重量") if weight is not None else None,
        "dimensions_cm": dimensions if isinstance(dimensions, dict) else {},
        "skus": skus,
        "data_mode": "real",
        "source_provider": "browser",
    }


def parse_1688_snapshot(snapshot: dict[str, Any], source_url: str) -> dict[str, Any]:
    """Extract one requested offer from observed JSON; fail on missing facts."""
    parsed = urlparse(source_url)
    match = _OFFER_PATH.fullmatch(parsed.path)
    if not match or parsed.hostname != "detail.1688.com" or parsed.scheme not in {"http", "https"}:
        raise IntegrationError("真实采集仅支持 detail.1688.com/offer/商品编号.html")
    expected_id = match.group(1)
    actual_url = str(snapshot.get("url", source_url))
    actual_path = urlparse(actual_url).path
    title = str(snapshot.get("title", ""))
    text = str(snapshot.get("text", ""))
    html = str(snapshot.get("html", ""))
    if "_____tmd_____" in actual_path or re.search(r'"action"\s*:\s*"captcha"', html) or any(
        phrase in title for phrase in ("验证码", "访问验证", "安全验证", "滑块验证")
    ):
        raise IntegrationError("1688 要求完成访问验证，请在采集浏览器手动验证后重试；未保存商品")
    if "login.1688.com" in actual_url or "login.taobao.com" in actual_url or (
        "登录" in title and "商品" not in title
    ):
        raise IntegrationError("1688 要求登录，请在采集浏览器手动登录后重试；未保存商品")
    if any(phrase in text for phrase in ("该商品已下架", "商品不存在", "商品已删除")):
        raise IntegrationError("1688 商品已下架或不存在，未保存商品")
    actual = urlparse(actual_url)
    actual_match = _OFFER_PATH.fullmatch(actual.path)
    if actual.hostname != "detail.1688.com" or not actual_match or actual_match.group(1) != expected_id:
        raise IntegrationError("浏览器当前页面不是所请求的 1688 商品，未保存商品")

    page = _PageHTML()
    page.feed(html)
    roots: list[Any] = [snapshot.get("globals", {})]
    roots.extend(snapshot.get("responses", []) if isinstance(snapshot.get("responses"), list) else [])
    scripts = snapshot.get("scripts", [])
    for script in [*page.scripts, *(scripts if isinstance(scripts, list) else [])]:
        if isinstance(script, str):
            roots.extend(_decode_json(script))
    errors: list[IntegrationError] = []
    for root in roots:
        if isinstance(root, str):
            decoded = _decode_json(root)
            root = decoded[0] if decoded else {}
        for anchor, _ in _walk(root, expected_id):
            if _offer_id(anchor) != expected_id:
                continue
            # Never borrow facts from ancestors: sibling modules may be ads or
            # recommendations and have no proven relationship to this offer.
            if _find(anchor, _SKU_KEYS, expected_id) is None:
                continue
            try:
                return _parse_candidate(anchor, anchor, expected_id, source_url, page)
            except IntegrationError as exc:
                errors.append(exc)
    if errors:
        raise errors[-1]
    raise IntegrationError(
        "未读取到与该链接匹配的真实 1688 商品及 SKU 数据；请确认来源页已加载完整。"
        "当前页面结构可能暂不支持，未保存商品"
    )
