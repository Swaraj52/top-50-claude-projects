"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False, unique=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", name="uq_collections_user_name"),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("kind", sa.String(length=12), nullable=False, server_default="note"),
        sa.Column("origin", sa.String(length=12), nullable=False, server_default="written"),
        sa.Column("source_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("author", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("tags", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("starred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('note', 'article', 'reference', 'snippet')", name="ck_items_kind"),
        sa.CheckConstraint(
            "origin IN ('written', 'uploaded', 'imported', 'bookmark')", name="ck_items_origin"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_items_user_updated", "items", ["user_id", "updated_at"])
    op.create_index("ix_items_user_kind", "items", ["user_id", "kind"])
    op.create_index("ix_items_collection", "items", ["collection_id"])


def downgrade() -> None:
    op.drop_index("ix_items_collection", table_name="items")
    op.drop_index("ix_items_user_kind", table_name="items")
    op.drop_index("ix_items_user_updated", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_collections_user_id", table_name="collections")
    op.drop_table("collections")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
