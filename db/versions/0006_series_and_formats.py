"""series grouping + video format on content_packages

Revision ID: 0006_series_and_formats
Revises: 0005_render_metadata
Create Date: 2026-04-16

Adds:
  * `series` table — grouping primitive for multipart books, themed lists, rankings.
  * `series_books` join table — for series that span multiple books.
  * `content_packages.series_id`, `.part_number`, `.format` — attach packages
    to a series and tag their video format. Existing rows are backfilled with
    format = "short_hook".
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_series_and_formats"
down_revision: Union[str, None] = "0005_render_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("series_type", sa.String(length=32), nullable=False),
        sa.Column("source_book_id", sa.Integer(), nullable=True),
        sa.Column("source_author", sa.String(length=300), nullable=True),
        sa.Column("total_parts", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_book_id"], ["books.id"]),
    )
    op.create_index("ix_series_slug", "series", ["slug"], unique=True)

    op.create_table(
        "series_books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"]),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.UniqueConstraint(
            "series_id", "position", name="uq_series_books_position"
        ),
    )
    op.create_index(
        "ix_series_books_series_id", "series_books", ["series_id"]
    )
    op.create_index(
        "ix_series_books_book_id", "series_books", ["book_id"]
    )

    with op.batch_alter_table("content_packages") as batch:
        batch.add_column(sa.Column("series_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("part_number", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "format",
                sa.String(length=32),
                nullable=False,
                server_default="short_hook",
            )
        )
        batch.create_foreign_key(
            "fk_content_packages_series_id",
            "series",
            ["series_id"],
            ["id"],
        )
        batch.create_index(
            "ix_content_packages_series_id", ["series_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("content_packages") as batch:
        batch.drop_index("ix_content_packages_series_id")
        batch.drop_constraint("fk_content_packages_series_id", type_="foreignkey")
        batch.drop_column("format")
        batch.drop_column("part_number")
        batch.drop_column("series_id")

    op.drop_index("ix_series_books_book_id", table_name="series_books")
    op.drop_index("ix_series_books_series_id", table_name="series_books")
    op.drop_table("series_books")

    op.drop_index("ix_series_slug", table_name="series")
    op.drop_table("series")
