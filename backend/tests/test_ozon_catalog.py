import pytest

from app.database.session import Database
from app.repositories.ozon_catalog import OzonCatalogRepository
from app.services.ozon_catalog import (
    OzonCatalogService,
    flatten_tree,
    normalize_attribute,
)


@pytest.fixture
def repo():
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = database.session_factory()
    try:
        yield OzonCatalogRepository(session)
    finally:
        session.close()


class FakeClient:
    def __init__(self, tree: list[dict], attributes: dict[int, list[dict]]):
        self.tree = tree
        self.attributes = attributes

    def category_tree(self, language: str = "ZH_HANS"):
        assert language
        return self.tree

    def category_attributes(self, category_id: int, language: str = "RU"):
        return self.attributes.get(category_id, [])


def test_flatten_tree():
    tree = [
        {
            "category_id": 1,
            "title": "服装",
            "children": [
                {"category_id": 2, "title": "男装", "children": []},
                {
                    "category_id": 3,
                    "title": "女装",
                    "children": [{"category_id": 4, "title": "连衣裙"}],
                },
            ],
        }
    ]
    nodes = flatten_tree(tree)
    by_id = {node["category_id"]: node for node in nodes}
    assert len(nodes) == 4
    assert by_id[4]["name"] == "连衣裙"
    assert by_id[4]["parent_category_id"] == 3
    assert by_id[4]["level"] == 2
    assert by_id[1]["parent_category_id"] is None
    assert by_id[1]["level"] == 0


def test_sync_tree_writes_categories(repo):
    service = OzonCatalogService(repo)
    client = FakeClient(
        [{"category_id": 10, "title": "鞋", "children": []}], {}
    )
    result = service.sync_tree(client)
    assert result == {"categories": 1}
    found = repo.search_categories("鞋")
    assert len(found) == 1
    assert found[0].category_id == 10


def _synced_service(repo, category_id: int = 17034433) -> OzonCatalogService:
    service = OzonCatalogService(repo)
    # Attributes have a FK to the category row, so sync the tree first.
    service.sync_tree(
        FakeClient(
            [{"category_id": category_id, "title": "测试类目", "children": []}], {}
        )
    )
    client = FakeClient(
        [],
        {
            category_id: [
                {
                    "id": 8229,
                    "name": "尺寸",
                    "is_required": True,
                    "type": "string",
                    "values": [
                        {"id": 1001, "value": "S"},
                        {"id": 1002, "value": "M"},
                    ],
                },
                {
                    "id": 10096,
                    "name": "材质",
                    "is_required": False,
                    "type": "string",
                    "values": [],
                },
                {
                    "id": 4158,
                    "name": "颜色",
                    "is_required": False,
                    "type": "string",
                    "values": [{"id": 2001, "value": "红色"}],
                },
            ]
        },
    )
    result = service.sync_attributes(client, category_id)
    assert result == {
        "category_id": category_id,
        "attributes": 3,
        "required": 1,
    }
    return service


def test_sync_attributes_caches_definitions(repo):
    _synced_service(repo)
    attrs = repo.get_attributes(17034433)
    assert len(attrs) == 3
    size = next(a for a in attrs if a.attribute_id == 8229)
    assert size.name == "尺寸"
    assert size.is_required is True
    assert len(size.dictionary_values) == 2


def test_resolve_attributes_dictionary_match(repo):
    service = _synced_service(repo)
    resolved, unmapped, missing = service.resolve_attributes(
        17034433, {"尺寸": "M", "材质": "棉", "颜色": "红色"}
    )
    by_id = {a["id"]: a for a in resolved}
    assert by_id[8229] == {
        "id": 8229,
        "values": [{"dictionary_value_id": 1002}],
    }
    assert by_id[10096] == {"id": 10096, "values": [{"value": "棉"}]}
    assert by_id[4158]["values"][0]["dictionary_value_id"] == 2001
    assert unmapped == []
    assert missing == []


def test_resolve_attributes_missing_required(repo):
    service = _synced_service(repo)
    resolved, unmapped, missing = service.resolve_attributes(17034433, {})
    assert resolved == []
    assert unmapped == []
    assert missing == ["尺寸"]


def test_resolve_attributes_dictionary_miss_falls_back_to_text(repo):
    service = _synced_service(repo)
    resolved, unmapped, missing = service.resolve_attributes(
        17034433, {"尺寸": "XXL"}
    )
    by_id = {a["id"]: a for a in resolved}
    assert by_id[8229] == {"id": 8229, "values": [{"value": "XXL"}]}
    assert unmapped == []
    assert missing == []


def test_resolve_attributes_unknown_names_are_unmapped(repo):
    service = _synced_service(repo)
    resolved, unmapped, missing = service.resolve_attributes(
        17034433, {"尺寸": "M", "不存在的属性": "x"}
    )
    assert unmapped == ["不存在的属性"]
    assert missing == []
    assert {a["id"] for a in resolved} == {8229}


def test_resolve_attributes_without_cache_marks_unmapped(repo):
    service = OzonCatalogService(repo)
    resolved, unmapped, missing = service.resolve_attributes(
        999, {"任意属性": "任意值"}
    )
    assert resolved == []
    assert unmapped == ["任意属性"]
    assert missing == []


def test_normalize_attribute_defaults():
    normalized = normalize_attribute({"id": 5})
    assert normalized == {
        "attribute_id": 5,
        "name": "",
        "is_required": False,
        "type": "",
        "dictionary_values": [],
    }
