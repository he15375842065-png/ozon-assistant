from typing import Any, Literal


def source_data_kind(source: str, payload: dict[str, Any]) -> Literal["mock", "real"]:
    """Identify sample records, including ones written before provenance existed."""

    if source == "mock_1688" or payload.get("mock") is True:
        return "mock"
    if payload.get("provider") == "mock_1688":
        return "mock"
    # Old sample payloads used source=1688 and had no explicit marker. Match the
    # full fixed fixture signature rather than assuming all old products are mock.
    images = payload.get("images", [])
    if (
        payload.get("title") == "多功能家居收纳盒 桌面化妆品整理盒"
        and payload.get("supplier") == "义乌市简居日用品厂"
        and isinstance(images, list)
        and bool(images)
        and all(isinstance(url, str) and url.startswith("https://placehold.co/") for url in images)
    ):
        return "mock"
    return "real"


def source_data_provider(source: str, payload: dict[str, Any]) -> str:
    if source_data_kind(source, payload) == "mock":
        return "mock_1688"
    return str(payload.get("provider") or "1688")
