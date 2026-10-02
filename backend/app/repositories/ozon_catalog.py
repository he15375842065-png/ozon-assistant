"""Persistence for Ozon catalog metadata synced from the Seller API."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database.base import utc_now
from app.models import OzonCategory, OzonCategoryAttribute


class OzonCatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- categories -----------------------------------------------------

    def upsert_categories(self, nodes: Sequence[dict]) -> int:
        """Insert or update flattened category nodes. Returns count written."""
        now = utc_now()
        written = 0
        for node in nodes:
            category_id = int(node["category_id"])
            existing = self.session.scalar(
                select(OzonCategory).where(OzonCategory.category_id == category_id)
            )
            if existing is None:
                self.session.add(
                    OzonCategory(
                        category_id=category_id,
                        name=str(node.get("name", "")),
                        parent_category_id=node.get("parent_category_id"),
                        level=int(node.get("level", 0)),
                        synced_at=now,
                    )
                )
            else:
                existing.name = str(node.get("name", ""))
                existing.parent_category_id = node.get("parent_category_id")
                existing.level = int(node.get("level", 0))
                existing.synced_at = now
            written += 1
        self.session.flush()
        return written

    def get_category(self, category_id: int) -> OzonCategory | None:
        return self.session.scalar(
            select(OzonCategory)
            .options(selectinload(OzonCategory.attributes))
            .where(OzonCategory.category_id == category_id)
        )

    def search_categories(self, query: str, limit: int = 20) -> Sequence[OzonCategory]:
        like = f"%{query}%"
        try:
            as_id = int(query)
        except ValueError:
            as_id = None
        filters = [OzonCategory.name.ilike(like)]
        if as_id is not None:
            filters.append(OzonCategory.category_id == as_id)
        return (
            self.session.scalars(
                select(OzonCategory)
                .where(or_(*filters))
                .order_by(OzonCategory.level.desc(), OzonCategory.name)
                .limit(limit)
            ).all()
        )

    def category_count(self) -> int:
        return self.session.scalar(select(func.count(OzonCategory.id))) or 0

    def last_category_sync(self) -> datetime | None:
        return self.session.scalar(select(func.max(OzonCategory.synced_at)))

    # -- attributes -------------------------------------------------------

    def upsert_attributes(
        self, category_id: int, attrs: Sequence[dict]
    ) -> int:
        now = utc_now()
        written = 0
        for attr in attrs:
            attribute_id = int(attr["attribute_id"])
            existing = self.session.scalar(
                select(OzonCategoryAttribute).where(
                    OzonCategoryAttribute.category_id == category_id,
                    OzonCategoryAttribute.attribute_id == attribute_id,
                )
            )
            values = attr.get("dictionary_values") or []
            if existing is None:
                self.session.add(
                    OzonCategoryAttribute(
                        category_id=category_id,
                        attribute_id=attribute_id,
                        name=str(attr.get("name", "")),
                        is_required=bool(attr.get("is_required", False)),
                        attribute_type=str(attr.get("type", "")),
                        dictionary_values=list(values),
                        synced_at=now,
                    )
                )
            else:
                existing.name = str(attr.get("name", ""))
                existing.is_required = bool(attr.get("is_required", False))
                existing.attribute_type = str(attr.get("type", ""))
                existing.dictionary_values = list(values)
                existing.synced_at = now
            written += 1
        self.session.flush()
        return written

    def get_attributes(self, category_id: int) -> Sequence[OzonCategoryAttribute]:
        return (
            self.session.scalars(
                select(OzonCategoryAttribute)
                .where(OzonCategoryAttribute.category_id == category_id)
                .order_by(
                    OzonCategoryAttribute.is_required.desc(),
                    OzonCategoryAttribute.name,
                )
            ).all()
        )

    def clear_attributes(self, category_id: int) -> None:
        for attr in self.get_attributes(category_id):
            self.session.delete(attr)
        self.session.flush()
