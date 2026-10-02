import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import ValidationError
from app.integrations.sources import (
    Alibaba1688Adapter,
    Mock1688Provider,
    NormalizedProductData,
    NormalizedVariantData,
)


def test_mock_1688_adapter_is_deterministic_and_normalized() -> None:
    adapter = Alibaba1688Adapter(Mock1688Provider())
    url = "https://detail.1688.com/offer/123456789.html"

    first = adapter.collect(url)
    second = adapter.collect(url)

    assert first == second
    assert first.source == "mock_1688"
    assert first.raw_payload["mock"] is True
    assert first.raw_payload["provider"] == "mock_1688"
    assert first.source_product_id == "123456789"
    assert len(first.variants) == 2
    assert first.stock == sum(item.stock for item in first.variants)
    assert first.purchase_price == min(item.purchase_price for item in first.variants)


def test_mock_1688_adapter_rejects_other_domains() -> None:
    adapter = Alibaba1688Adapter(Mock1688Provider())

    with pytest.raises(ValidationError, match="1688.com"):
        adapter.collect("https://example.com/offer/123.html")


def test_normalized_product_enforces_stock_and_asset_invariants() -> None:
    variant = NormalizedVariantData(
        source_sku_id="sku-1",
        name="Variant",
        purchase_price=10,
        stock=3,
        image="https://example.com/sku.jpg",
    )
    common = {
        "source": "1688",
        "source_product_id": "123",
        "source_url": "https://detail.1688.com/offer/123.html",
        "title_original": "Product",
        "purchase_price": 10,
        "variants": [variant],
        "stock": 3,
    }

    with pytest.raises(PydanticValidationError, match="sum of variant stock"):
        NormalizedProductData(**{**common, "stock": 4})

    with pytest.raises(PydanticValidationError, match="asset URLs"):
        NormalizedProductData(**{**common, "images": ["javascript:alert(1)"]})

