"""V2: Ozon category metadata tables + draft weight/dimensions.

Revision ID: 20261002_0002
Revises: 20261001_0001
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0002"
down_revision: str | None = "20261001_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ozon_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("parent_category_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ozon_categories"),
    )
    op.create_index(
        "ix_ozon_categories_category_id",
        "ozon_categories",
        ["category_id"],
        unique=True,
    )
    op.create_index(
        "ix_ozon_categories_parent_category_id",
        "ozon_categories",
        ["parent_category_id"],
    )

    op.create_table(
        "ozon_category_attributes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("attribute_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("attribute_type", sa.String(length=60), nullable=False),
        sa.Column("dictionary_values", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["ozon_categories.category_id"],
            name="fk_ozon_category_attributes_category",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ozon_category_attributes"),
        sa.UniqueConstraint(
            "category_id", "attribute_id", name="uq_category_attribute"
        ),
    )
    op.create_index(
        "ix_ozon_category_attributes_category",
        "ozon_category_attributes",
        ["category_id"],
    )

    op.add_column(
        "ozon_drafts", sa.Column("weight_g", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ozon_drafts", sa.Column("length_mm", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ozon_drafts", sa.Column("width_mm", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ozon_drafts", sa.Column("height_mm", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ozon_drafts", "height_mm")
    op.drop_column("ozon_drafts", "width_mm")
    op.drop_column("ozon_drafts", "length_mm")
    op.drop_column("ozon_drafts", "weight_g")
    op.drop_index("ix_ozon_category_attributes_category", table_name="ozon_category_attributes")
    op.drop_table("ozon_category_attributes")
    op.drop_index("ix_ozon_categories_parent_category_id", table_name="ozon_categories")
    op.drop_index("ix_ozon_categories_category_id", table_name="ozon_categories")
    op.drop_table("ozon_categories")
