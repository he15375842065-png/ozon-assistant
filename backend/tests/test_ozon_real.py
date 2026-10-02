import pytest

from app.integrations.ozon.base import OzonPublishResult
from app.integrations.ozon.client import OzonAPIError
from app.integrations.ozon.real import RealOzonConnector


class FakeOzonClient:
    def __init__(self):
        self.imported: list[dict] = []
        self.info_calls = 0

    def import_products(self, items: list[dict]) -> int:
        self.imported.extend(items)
        return 4242

    def import_info(self, task_id: int) -> dict:
        assert task_id == 4242
        self.info_calls += 1
        return {
            "items": [
                {
                    "offer_id": self.imported[0]["offer_id"],
                    "status": "imported",
                    "product_id": 98765,
                }
            ]
        }


class FakeResolver:
    """Mimics OzonCatalogService.resolve_attributes.

    Returns (resolved, unmapped_names, missing_required_names).
    """

    def __init__(self, missing_required: list[str] | None = None):
        self.missing_required = missing_required or []

    def resolve_attributes(
        self, category_id: int, attributes: dict
    ) -> tuple[list[dict], list[str], list[str]]:
        return (
            [{"id": 8229, "values": [{"value": "M"}]}],
            [],
            list(self.missing_required),
        )


def _payload(**overrides):
    base = {
        "title": "男士棉T恤",
        "description": "纯棉短袖",
        "category_id": "17034433",
        "attributes": {"尺寸": "M"},
        "variants": [
            {
                "offer_id": "DRAFT-1",
                "sku": "SKU-1",
                "source_sku_id": "S1",
                "name": "M",
                "color": "白色",
                "size": "M",
                "price": 99.0,
                "stock": 10,
                "image": "https://example.com/img.jpg",
            }
        ],
        "images": ["https://example.com/img.jpg"],
        "price": 99.0,
        "stock": 10,
        "weight_g": 300,
        "length_mm": 200,
        "width_mm": 150,
        "height_mm": 50,
    }
    base.update(overrides)
    return base


def test_publish_draft_happy_path():
    client = FakeOzonClient()
    connector = RealOzonConnector(client, attribute_resolver=FakeResolver())
    result = connector.publish_draft(1, _payload())
    assert isinstance(result, OzonPublishResult)
    assert result.publication_id == "98765"
    assert result.status == "published"
    assert result.response["mock"] is False
    assert result.response["task_id"] == 4242
    assert result.response["warnings"] == []

    (item,) = client.imported
    assert "_warnings" not in item  # internal field must not leak to Ozon
    assert item["offer_id"] == "OA-1"
    assert item["category_id"] == 17034433
    assert item["weight"] == 300
    assert item["weight_unit"] == "g"
    assert item["dimension_unit"] == "mm"
    assert item["depth"] == 200
    assert item["width"] == 150
    assert item["height"] == 50
    assert item["attributes"] == [{"id": 8229, "values": [{"value": "M"}]}]
    assert item["price"] == "99.00"
    assert item["images"] == ["https://example.com/img.jpg"]


def test_publish_draft_requires_weight():
    client = FakeOzonClient()
    connector = RealOzonConnector(client, attribute_resolver=FakeResolver())
    with pytest.raises(OzonAPIError, match="重量"):
        connector.publish_draft(1, _payload(weight_g=None))


def test_publish_draft_requires_numeric_category():
    client = FakeOzonClient()
    connector = RealOzonConnector(client, attribute_resolver=FakeResolver())
    with pytest.raises(OzonAPIError, match="类目"):
        connector.publish_draft(1, _payload(category_id="服装"))


def test_publish_draft_requires_positive_price():
    client = FakeOzonClient()
    connector = RealOzonConnector(client, attribute_resolver=FakeResolver())
    with pytest.raises(OzonAPIError, match="价格"):
        connector.publish_draft(1, _payload(price=0))


def test_publish_draft_warns_on_missing_required_attributes():
    client = FakeOzonClient()
    connector = RealOzonConnector(
        client, attribute_resolver=FakeResolver(missing_required=["尺寸"])
    )
    result = connector.publish_draft(1, _payload())
    assert result.status == "published"
    assert any("尺寸" in warning for warning in result.response["warnings"])


def test_publish_draft_warns_on_non_public_images():
    client = FakeOzonClient()
    connector = RealOzonConnector(client, attribute_resolver=FakeResolver())
    result = connector.publish_draft(1, _payload(images=["not-a-url"]))
    assert result.status == "published"
    assert any("公开图片" in warning for warning in result.response["warnings"])
    (item,) = client.imported
    assert item["images"] == []


def test_publish_draft_rejected_by_ozon():
    class RejectingClient(FakeOzonClient):
        def import_info(self, task_id: int) -> dict:
            return {
                "items": [
                    {
                        "offer_id": self.imported[0]["offer_id"],
                        "status": "failed",
                        "errors": [{"code": "E1", "message": "标题太短"}],
                    }
                ]
            }

    connector = RealOzonConnector(
        RejectingClient(), attribute_resolver=FakeResolver()
    )
    with pytest.raises(RuntimeError, match="标题太短"):
        connector.publish_draft(1, _payload())


def test_publish_draft_timeout():
    class SlowClient(FakeOzonClient):
        def import_info(self, task_id: int) -> dict:
            return {"items": []}

    connector = RealOzonConnector(
        SlowClient(),
        attribute_resolver=FakeResolver(),
        poll_timeout_s=0.01,
        poll_interval_s=0.001,
    )
    with pytest.raises(RuntimeError, match="超时"):
        connector.publish_draft(1, _payload())
