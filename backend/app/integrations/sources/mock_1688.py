import hashlib
import re
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

from app.core.errors import IntegrationError, ValidationError
from app.integrations.sources.base import (
    NormalizedProductData,
    NormalizedVariantData,
    ProductSourceAdapter,
)


class Alibaba1688DataProvider(ABC):
    @abstractmethod
    def fetch(self, url: str) -> dict[str, Any]:
        """Return provider-specific raw product data."""


class Mock1688Provider(Alibaba1688DataProvider):
    """Deterministic provider used to exercise the complete local workflow."""

    _OFFER_ID = re.compile(r"/offer/(\d+)(?:\.html)?", re.IGNORECASE)

    def fetch(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValidationError("请输入有效的 1688 商品链接")
        if parsed.hostname != "1688.com" and not parsed.hostname.endswith(".1688.com"):
            raise ValidationError("当前采集器仅支持 1688.com 商品链接")

        offer_match = self._OFFER_ID.search(parsed.path)
        offer_id = (
            offer_match.group(1)
            if offer_match
            else hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        )
        seed = int(hashlib.sha256(offer_id.encode("utf-8")).hexdigest()[:8], 16)
        base_price = round(28 + (seed % 2200) / 100, 2)
        stock_a = 80 + seed % 320
        stock_b = 60 + (seed // 7) % 240
        image = "https://placehold.co/800x800/eef2ff/4f46e5?text=1688+Product"
        image_alt = "https://placehold.co/800x800/f8fafc/0f172a?text=Product+Detail"
        return {
            "offer_id": offer_id,
            "url": url,
            "title": "多功能家居收纳盒 桌面化妆品整理盒",
            "description": "加厚环保材质，分区设计，可用于桌面、卧室和浴室收纳。",
            "category": "日用百货 > 收纳整理 > 收纳盒",
            "supplier": "义乌市简居日用品厂",
            "currency": "CNY",
            "images": [image, image_alt],
            "videos": [],
            "attributes": {
                "材质": "PP",
                "风格": "简约",
                "适用场景": "桌面收纳",
                "产地": "浙江义乌",
            },
            "weight_kg": 0.72,
            "dimensions_cm": {"length": 28.0, "width": 18.0, "height": 14.0},
            "skus": [
                {
                    "sku_id": f"{offer_id}-WHITE",
                    "name": "奶油白 / 标准款",
                    "color": "奶油白",
                    "size": "标准款",
                    "price": base_price,
                    "stock": stock_a,
                    "image": image,
                },
                {
                    "sku_id": f"{offer_id}-GREEN",
                    "name": "薄荷绿 / 标准款",
                    "color": "薄荷绿",
                    "size": "标准款",
                    "price": round(base_price + 2.0, 2),
                    "stock": stock_b,
                    "image": image_alt,
                },
            ],
        }


class Alibaba1688Adapter(ProductSourceAdapter):
    def __init__(self, provider: Alibaba1688DataProvider) -> None:
        self.provider = provider

    def collect(self, url: str) -> NormalizedProductData:
        try:
            raw = self.provider.fetch(url)
            variants = [
                NormalizedVariantData(
                    source_sku_id=str(item["sku_id"]),
                    name=str(item["name"]),
                    color=item.get("color"),
                    size=item.get("size"),
                    purchase_price=float(item["price"]),
                    stock=int(item["stock"]),
                    image=item.get("image"),
                )
                for item in raw.get("skus", [])
            ]
            if not variants:
                raise IntegrationError("1688 商品没有可用 SKU")
            return NormalizedProductData(
                source="1688",
                source_product_id=str(raw["offer_id"]),
                source_url=raw["url"],
                title_original=str(raw["title"]),
                description_original=str(raw.get("description", "")),
                category_original=raw.get("category"),
                supplier=raw.get("supplier"),
                purchase_price=min(variant.purchase_price for variant in variants),
                currency=str(raw.get("currency", "CNY")),
                images=list(raw.get("images", [])),
                videos=list(raw.get("videos", [])),
                variants=variants,
                attributes=dict(raw.get("attributes", {})),
                stock=sum(variant.stock for variant in variants),
                weight_kg=raw.get("weight_kg"),
                dimensions_cm=dict(raw.get("dimensions_cm", {})),
                raw_payload=raw,
            )
        except (ValidationError, IntegrationError):
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationError("1688 返回的数据格式不完整") from exc

