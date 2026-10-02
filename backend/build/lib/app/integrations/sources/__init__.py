from app.integrations.sources.base import (
    NormalizedProductData,
    NormalizedVariantData,
    ProductSourceAdapter,
)
from app.integrations.sources.mock_1688 import Alibaba1688Adapter, Mock1688Provider
from app.integrations.sources.browser_1688 import Browser1688Provider

__all__ = [
    "Alibaba1688Adapter",
    "Mock1688Provider",
    "Browser1688Provider",
    "NormalizedProductData",
    "NormalizedVariantData",
    "ProductSourceAdapter",
]

