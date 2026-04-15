"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-15

Creates the full Phase 1 schema:
  books, book_sources, content_packages, videos, analytics.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=300), nullable=False),
        sa.Column("isbn", sa.String(length=32), nullable=True),
        sa.Column("asin", sa.String(length=32), nullable=True),
        sa.Column("cover_url", sa.String(length=1000), nullable=True),
        sa.Column("description", sa.String(length=4000), nullable=True),
        sa.Column("genre", sa.String(length=64), nullable=True),
        sa.Column("genre_confidence", sa.Float(), nullable=True),
        sa.Column("genre_override", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="discovered"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_books_isbn", "books", ["isbn"])
    op.create_index("ix_books_asin", "books", ["asin"])

    op.create_table(
        "book_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
    )
    op.create_index("ix_book_sources_book_id", "book_sources", ["book_id"])

    op.create_table(
        "content_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column("visual_prompts", sa.JSON(), nullable=True),
        sa.Column("narration", sa.Text(), nullable=True),
        sa.Column("titles", sa.JSON(), nullable=True),
        sa.Column("hashtags", sa.JSON(), nullable=True),
        sa.Column("affiliate_amazon", sa.String(length=1000), nullable=True),
        sa.Column("affiliate_bookshop", sa.String(length=1000), nullable=True),
        sa.Column("regenerate_note", sa.Text(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
    )
    op.create_index("ix_content_packages_book_id", "content_packages", ["book_id"])

    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["package_id"], ["content_packages.id"]),
    )
    op.create_index("ix_videos_book_id", "videos", ["book_id"])

    op.create_table(
        "analytics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("watch_time_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affiliate_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revenue_cents", sa.Float(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
    )
    op.create_index("ix_analytics_video_id", "analytics", ["video_id"])


def downgrade() -> None:
    op.drop_index("ix_analytics_video_id", table_name="analytics")
    op.drop_table("analytics")
    op.drop_index("ix_videos_book_id", table_name="videos")
    op.drop_table("videos")
    op.drop_index("ix_content_packages_book_id", table_name="content_packages")
    op.drop_table("content_packages")
    op.drop_index("ix_book_sources_book_id", table_name="book_sources")
    op.drop_table("book_sources")
    op.drop_index("ix_books_asin", table_name="books")
    op.drop_index("ix_books_isbn", table_name="books")
    op.drop_table("books")
