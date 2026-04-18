"""content_items: rename books→content_items, move book fields into JSON

Revision ID: 0010_content_items
Revises: 0009_profiles
Create Date: 2026-04-18

Phase B2 of the generalization plan. Restructures the pipeline's
primary entity from book-specific to niche-agnostic:

  books           → content_items    (+ profile_id FK, + research JSON)
  book_sources    → content_item_sources
  content_packages.book_id   → content_item_id
  videos.book_id             → content_item_id
  series.source_book_id      → source_content_item_id
  series_books.book_id       → content_item_id

The `author` column becomes `subtitle` (generic secondary-label slot —
"author" for books, "director" for films, "cuisine" for recipes, etc.).

Book-specific fields `isbn`, `asin`, `genre`, `genre_confidence`,
`genre_override`, `dossier` collapse into a single `research` JSON blob
on the content_item. For existing rows (Books profile) the JSON
preserves every field so no data is lost. Callers that used to read
`book.genre` now read `item.research.get("genre")` — see the
`ContentItem` model for convenience accessors.

`profile_id` defaults to the `books` profile seeded in 0009 so existing
installs stay internally consistent after upgrade.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_content_items"
down_revision: Union[str, None] = "0009_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BOOK_FIELDS_MOVED_TO_RESEARCH = (
    "isbn",
    "asin",
    "genre",
    "genre_confidence",
    "genre_override",
    "dossier",
)


def _books_profile_id(conn: sa.Connection) -> int:
    row = conn.execute(
        sa.text("SELECT id FROM profiles WHERE slug = 'books'")
    ).fetchone()
    if row is None:
        # 0009 always seeds this row; the only way here is if a user
        # hand-deleted it. Fail loudly rather than silently orphan items.
        raise RuntimeError(
            "migration 0010 requires the 'books' profile from 0009 "
            "(not found — did you drop it manually?)"
        )
    return int(row[0])


def upgrade() -> None:
    conn = op.get_bind()
    books_profile_id = _books_profile_id(conn)

    # ------------------------------------------------------------------
    # 1. content_items: rename books, add profile_id + research, move
    #    book-specific columns into research, drop them.
    # ------------------------------------------------------------------
    # Drop FKs on dependent tables first so the rename is unambiguous.
    # (SQLite's batch_alter recreates those tables on the other side of
    # the rename with the new target.)
    with op.batch_alter_table("content_packages") as batch:
        batch.drop_index("ix_content_packages_book_id")
    with op.batch_alter_table("videos") as batch:
        batch.drop_index("ix_videos_book_id")
    with op.batch_alter_table("book_sources") as batch:
        batch.drop_index("ix_book_sources_book_id")
    with op.batch_alter_table("series_books") as batch:
        batch.drop_index("ix_series_books_book_id")
    # Drop book-specific indexes on the soon-to-be-dropped columns; the
    # batch recreate on the renamed table would otherwise try to replay
    # `CREATE INDEX ix_books_isbn ON content_items (isbn)` against a
    # schema that no longer has the column.
    with op.batch_alter_table("books") as batch:
        batch.drop_index("ix_books_isbn")
        batch.drop_index("ix_books_asin")

    op.rename_table("books", "content_items")

    with op.batch_alter_table("content_items") as batch:
        batch.alter_column("author", new_column_name="subtitle")
        batch.add_column(sa.Column("profile_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("research", sa.JSON(), nullable=True))

    # Backfill profile_id for every existing item (all are Books) + pack
    # the six book-specific columns into the research JSON.
    op.execute(
        sa.text("UPDATE content_items SET profile_id = :pid").bindparams(
            pid=books_profile_id
        )
    )

    rows = conn.execute(
        sa.text(
            "SELECT id, isbn, asin, genre, genre_confidence, "
            "genre_override, dossier FROM content_items"
        )
    ).fetchall()
    for row in rows:
        research = {}
        for field in BOOK_FIELDS_MOVED_TO_RESEARCH:
            val = getattr(row, field, None)
            if val is None:
                continue
            if field == "dossier" and isinstance(val, str):
                # The column is JSON-typed; SQLite returns it as a string.
                try:
                    val = json.loads(val)
                except (TypeError, ValueError):
                    pass
            research[field] = val
        conn.execute(
            sa.text(
                "UPDATE content_items SET research = :r WHERE id = :i"
            ).bindparams(r=json.dumps(research) if research else None, i=row.id)
        )

    with op.batch_alter_table("content_items") as batch:
        batch.alter_column("profile_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_content_items_profile_id", "profiles", ["profile_id"], ["id"]
        )
        batch.create_index("ix_content_items_profile_id", ["profile_id"])
        for field in BOOK_FIELDS_MOVED_TO_RESEARCH:
            batch.drop_column(field)

    # ------------------------------------------------------------------
    # 2. book_sources → content_item_sources, rename book_id → content_item_id
    # ------------------------------------------------------------------
    op.rename_table("book_sources", "content_item_sources")
    # Rename the FK column in one batch. Re-creating the FK + index in
    # the same batch fails because alembic reflects the pre-rename
    # schema. Split into two batches: rename, then re-add.
    with op.batch_alter_table("content_item_sources") as batch:
        batch.alter_column("book_id", new_column_name="content_item_id")
    with op.batch_alter_table("content_item_sources") as batch:
        batch.create_foreign_key(
            "fk_content_item_sources_content_item_id",
            "content_items",
            ["content_item_id"],
            ["id"],
        )
        batch.create_index(
            "ix_content_item_sources_content_item_id", ["content_item_id"]
        )

    # ------------------------------------------------------------------
    # 3. Dependent FK column renames: content_packages, videos, series,
    #    series_books. batch_alter_table handles the SQLite recreate;
    #    same two-batch pattern as above.
    # ------------------------------------------------------------------
    with op.batch_alter_table("content_packages") as batch:
        batch.alter_column("book_id", new_column_name="content_item_id")
    with op.batch_alter_table("content_packages") as batch:
        batch.create_foreign_key(
            "fk_content_packages_content_item_id",
            "content_items",
            ["content_item_id"],
            ["id"],
        )
        batch.create_index(
            "ix_content_packages_content_item_id", ["content_item_id"]
        )

    with op.batch_alter_table("videos") as batch:
        batch.alter_column("book_id", new_column_name="content_item_id")
    with op.batch_alter_table("videos") as batch:
        batch.create_foreign_key(
            "fk_videos_content_item_id",
            "content_items",
            ["content_item_id"],
            ["id"],
        )
        batch.create_index("ix_videos_content_item_id", ["content_item_id"])

    with op.batch_alter_table("series") as batch:
        batch.alter_column(
            "source_book_id", new_column_name="source_content_item_id"
        )
    with op.batch_alter_table("series") as batch:
        batch.create_foreign_key(
            "fk_series_source_content_item_id",
            "content_items",
            ["source_content_item_id"],
            ["id"],
        )

    with op.batch_alter_table("series_books") as batch:
        batch.alter_column("book_id", new_column_name="content_item_id")
    with op.batch_alter_table("series_books") as batch:
        batch.create_foreign_key(
            "fk_series_books_content_item_id",
            "content_items",
            ["content_item_id"],
            ["id"],
        )
        batch.create_index(
            "ix_series_books_content_item_id", ["content_item_id"]
        )


def downgrade() -> None:
    # Intentionally not implemented — this migration moves data through
    # a JSON collapse, which is lossy in the reverse direction (the
    # research blob may have been edited post-upgrade). If you need to
    # downgrade, restore from a pre-upgrade backup.
    raise NotImplementedError(
        "downgrade from 0010 is lossy; restore from backup instead"
    )
