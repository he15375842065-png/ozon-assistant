from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utc_now


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class SourceProduct(Base):
    __tablename__ = "source_products"
    __table_args__ = (
        UniqueConstraint("source", "source_product_id", name="source_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    product: Mapped[Product | None] = relationship(
        back_populates="source_product",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_product_id: Mapped[int] = mapped_column(
        ForeignKey("source_products.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    title_original: Mapped[str] = mapped_column(String(500), nullable=False)
    description_original: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category_original: Mapped[str | None] = mapped_column(String(255))
    supplier: Mapped[str | None] = mapped_column(String(255))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    images: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    videos: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    dimensions_cm: Mapped[dict[str, float]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    ai_status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True, nullable=False
    )
    ozon_status: Mapped[str] = mapped_column(
        String(32), default="not_created", index=True, nullable=False
    )
    estimated_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_profit_margin: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))

    source_product: Mapped[SourceProduct] = relationship(back_populates="product")
    variants: Mapped[list[Variant]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="Variant.id",
    )
    ai_results: Mapped[list[AIResult]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="AIResult.created_at",
    )
    drafts: Mapped[list[OzonDraft]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="OzonDraft.created_at",
    )

    @property
    def latest_ai_result(self) -> AIResult | None:
        return max(
            self.ai_results,
            key=lambda result: result.id or 0,
            default=None,
        )

    @property
    def latest_draft(self) -> OzonDraft | None:
        return max(
            self.drafts,
            key=lambda draft: draft.id or 0,
            default=None,
        )


class Variant(TimestampMixin, Base):
    __tablename__ = "variants"
    __table_args__ = (
        UniqueConstraint("product_id", "source_sku_id", name="product_source_sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_sku_id: Mapped[str] = mapped_column(String(120), nullable=False)
    internal_sku: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(120))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="variants")


class AIResult(TimestampMixin, Base):
    __tablename__ = "ai_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    title_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    description_ru: Mapped[str] = mapped_column(Text, nullable=False)
    category_suggestion: Mapped[str] = mapped_column(String(255), nullable=False)
    category_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0"), nullable=False
    )
    attributes_suggestion: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    risk_level: Mapped[str] = mapped_column(String(20), default="low", nullable=False)
    risk_checks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    token_usage: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="ai_results")
    drafts: Mapped[list[OzonDraft]] = relationship(back_populates="ai_result")


class OzonDraft(TimestampMixin, Base):
    __tablename__ = "ozon_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ai_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_results.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[str] = mapped_column(String(120), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    variants: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    images: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    pricing: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="review", server_default="review", index=True, nullable=False
    )
    publication_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="drafts")
    ai_result: Mapped[AIResult | None] = relationship(back_populates="drafts")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_status_created_at", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppLog(Base):
    __tablename__ = "app_logs"
    __table_args__ = (Index("ix_app_logs_level_created_at", "level", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
