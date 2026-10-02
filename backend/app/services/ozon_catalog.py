"""Ozon catalog metadata sync and attribute resolution.

The category tree is synced in Chinese (``ZH_HANS``) so the user can browse it,
while attribute definitions are synced in Russian (``RU``) because draft
attributes are stored with Russian names by ``OzonAttributeMapper``.
"""

from __future__ import annotations

from typing import Any

from app.integrations.ozon.client import OzonSellerClient
from app.models import OzonCategoryAttribute
from app.repositories import LogRepository, OzonCatalogRepository


def flatten_tree(
    nodes: list[dict[str, Any]],
    *,
    parent_category_id: int | None = None,
    level: int = 0,
) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for node in nodes:
        category_id = int(node["category_id"])
        flat.append(
            {
                "category_id": category_id,
                "name": str(node.get("title") or node.get("name") or ""),
                "parent_category_id": parent_category_id,
                "level": level,
            }
        )
        children = node.get("children") or []
        flat.extend(
            flatten_tree(children, parent_category_id=category_id, level=level + 1)
        )
    return flat


def normalize_attribute(item: dict[str, Any]) -> dict[str, Any]:
    values = item.get("values") or item.get("dictionary_values") or []
    return {
        "attribute_id": int(item["id"]),
        "name": str(item.get("name") or ""),
        "is_required": bool(item.get("is_required", False)),
        "type": str(item.get("type") or ""),
        "dictionary_values": list(values) if isinstance(values, list) else [],
    }


class OzonCatalogService:
    def __init__(
        self, catalog: OzonCatalogRepository, logs: LogRepository | None = None
    ) -> None:
        self.catalog = catalog
        self.logs = logs

    def _log(self, level: str, source: str, message: str, context: dict) -> None:
        if self.logs is not None:
            self.logs.add(level, source, message, context)

    def sync_tree(self, client: OzonSellerClient) -> dict[str, Any]:
        tree = client.category_tree(language="ZH_HANS")
        nodes = flatten_tree(tree)
        written = self.catalog.upsert_categories(nodes)
        self._log("INFO", "Ozon", "Ozon 类目树同步完成", {"categories": written})
        return {"categories": written}

    def sync_attributes(
        self, client: OzonSellerClient, category_id: int
    ) -> dict[str, Any]:
        raw = client.category_attributes(category_id, language="RU")
        attrs = [normalize_attribute(item) for item in raw if "id" in item]
        # Replace stale definitions so removed attributes don't linger.
        self.catalog.clear_attributes(category_id)
        written = self.catalog.upsert_attributes(category_id, attrs)
        required = sum(1 for attr in attrs if attr["is_required"])
        self._log(
            "INFO",
            "Ozon",
            "Ozon 类目属性同步完成",
            {"category_id": category_id, "attributes": written, "required": required},
        )
        return {"category_id": category_id, "attributes": written, "required": required}

    def resolve_attributes(
        self, category_id: int, attributes: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        """Map draft attributes (Russian names) to Ozon attribute payloads.

        Returns ``(resolved, unmapped_names, missing_required_names)``.
        """
        definitions = self.catalog.get_attributes(category_id)
        by_name = {_norm_name(d.name): d for d in definitions}
        resolved: list[dict[str, Any]] = []
        unmapped: list[str] = []
        for name, value in attributes.items():
            definition = by_name.get(_norm_name(str(name)))
            if definition is None:
                unmapped.append(str(name))
                continue
            resolved.append(_build_attribute_value(definition, value))
        missing_required = [
            d.name
            for d in definitions
            if d.is_required and _norm_name(d.name) not in {_norm_name(str(k)) for k in attributes}
        ]
        return resolved, unmapped, missing_required


def _norm_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _build_attribute_value(
    definition: OzonCategoryAttribute, value: Any
) -> dict[str, Any]:
    text = str(value).strip()
    dict_id = _match_dictionary_value(definition.dictionary_values, text)
    if dict_id is not None:
        return {
            "id": definition.attribute_id,
            "values": [{"dictionary_value_id": dict_id}],
        }
    return {"id": definition.attribute_id, "values": [{"value": text}]}


def _match_dictionary_value(
    dictionary_values: list[dict[str, Any]], text: str
) -> int | None:
    wanted = _norm_name(text)
    for item in dictionary_values:
        candidate = item.get("value")
        if isinstance(candidate, str) and _norm_name(candidate) == wanted:
            value_id = item.get("id")
            if isinstance(value_id, int):
                return value_id
    return None
