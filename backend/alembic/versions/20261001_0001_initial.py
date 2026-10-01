"""Create the local MVP schema.

Revision ID: 20261001_0001
Revises:
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_app_logs"),
    )
    op.create_index("ix_app_logs_created_at", "app_logs", ["created_at"])
    op.create_index("ix_app_logs_level", "app_logs", ["level"])
    op.create_index("ix_app_logs_level_created_at", "app_logs", ["level", "created_at"])
    op.create_index("ix_app_logs_source", "app_logs", ["source"])

    op.create_table(
        "source_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_product_id", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_source_products"),
        sa.UniqueConstraint("source", "source_product_id", name="source_identity"),
    )
    op.create_index("ix_source_products_source", "source_products", ["source"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_status_created_at", "tasks", ["status", "created_at"])
    op.create_index("ix_tasks_task_type", "tasks", ["task_type"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_product_id", sa.Integer(), nullable=False),
        sa.Column("title_original", sa.String(length=500), nullable=False),
        sa.Column("description_original", sa.Text(), nullable=False),
        sa.Column("category_original", sa.String(length=255), nullable=True),
        sa.Column("supplier", sa.String(length=255), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("videos", sa.JSON(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("dimensions_cm", sa.JSON(), nullable=False),
        sa.Column("ai_status", sa.String(length=32), nullable=False),
        sa.Column("ozon_status", sa.String(length=32), nullable=False),
        sa.Column("estimated_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("estimated_profit_margin", sa.Numeric(precision=7, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_product_id"], ["source_products.id"],
            name="fk_products_source_product_id_source_products", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("source_product_id", name="uq_products_source_product_id"),
    )
    op.create_index("ix_products_ai_status", "products", ["ai_status"])
    op.create_index("ix_products_ozon_status", "products", ["ozon_status"])

    op.create_table(
        "variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_sku_id", sa.String(length=120), nullable=False),
        sa.Column("internal_sku", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("color", sa.String(length=120), nullable=True),
        sa.Column("size", sa.String(length=120), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_variants_product_id_products", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_variants"),
        sa.UniqueConstraint("internal_sku", name="uq_variants_internal_sku"),
        sa.UniqueConstraint("product_id", "source_sku_id", name="product_source_sku"),
    )
    op.create_index("ix_variants_product_id", "variants", ["product_id"])

    op.create_table(
        "ai_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("title_ru", sa.String(length=500), nullable=False),
        sa.Column("description_ru", sa.Text(), nullable=False),
        sa.Column("category_suggestion", sa.String(length=255), nullable=False),
        sa.Column("category_confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("attributes_suggestion", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("risk_checks", sa.JSON(), nullable=False),
        sa.Column("token_usage", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_ai_results_product_id_products", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_results"),
    )
    op.create_index("ix_ai_results_product_id", "ai_results", ["product_id"])

    op.create_table(
        "ozon_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("ai_result_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", sa.String(length=120), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("variants", sa.JSON(), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("pricing", sa.JSON(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="review", nullable=False
        ),
        sa.Column("publication_id", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_result_id"], ["ai_results.id"],
            name="fk_ozon_drafts_ai_result_id_ai_results", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_ozon_drafts_product_id_products", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ozon_drafts"),
        sa.UniqueConstraint("publication_id", name="uq_ozon_drafts_publication_id"),
    )
    op.create_index("ix_ozon_drafts_ai_result_id", "ozon_drafts", ["ai_result_id"])
    op.create_index("ix_ozon_drafts_product_id", "ozon_drafts", ["product_id"])
    op.create_index("ix_ozon_drafts_status", "ozon_drafts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ozon_drafts_status", table_name="ozon_drafts")
    op.drop_index("ix_ozon_drafts_product_id", table_name="ozon_drafts")
    op.drop_index("ix_ozon_drafts_ai_result_id", table_name="ozon_drafts")
    op.drop_table("ozon_drafts")
    op.drop_index("ix_ai_results_product_id", table_name="ai_results")
    op.drop_table("ai_results")
    op.drop_index("ix_variants_product_id", table_name="variants")
    op.drop_table("variants")
    op.drop_index("ix_products_ozon_status", table_name="products")
    op.drop_index("ix_products_ai_status", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_tasks_task_type", table_name="tasks")
    op.drop_index("ix_tasks_status_created_at", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_source_products_source", table_name="source_products")
    op.drop_table("source_products")
    op.drop_index("ix_app_logs_source", table_name="app_logs")
    op.drop_index("ix_app_logs_level_created_at", table_name="app_logs")
    op.drop_index("ix_app_logs_level", table_name="app_logs")
    op.drop_index("ix_app_logs_created_at", table_name="app_logs")
    op.drop_table("app_logs")
