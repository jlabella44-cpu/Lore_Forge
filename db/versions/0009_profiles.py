"""profiles: generic content niche config (books becomes the first one)

Revision ID: 0009_profiles
Revises: 0008_book_dossier
Create Date: 2026-04-18

Phase B1 of the generalization plan. Adds a `profiles` table that
later migrations and services will read instead of the hard-coded
"book trailer" assumptions in prompts, discovery sources, and the UI.

The upgrade seeds a single `Books` profile so existing installs keep
working byte-for-byte — the Books row mirrors what's currently in code
(genre list, tone map, Amazon + Bookshop CTAs, the five NYT/Goodreads/
BookTok/Amazon/Reddit source slugs). Later phases (B4 prompts, B5
source plugins) populate the rest.
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_profiles"
down_revision: Union[str, None] = "0008_book_dossier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mirrors backend/app/services/renderer.py GENRE_TONE at time of seeding.
# Duplicated on purpose — later migrations shouldn't silently shift based
# on application-side constants.
_BOOKS_RENDER_TONES = {
    "fantasy": "dark",
    "thriller": "dark",
    "scifi": "hype",
    "romance": "cozy",
    "historical_fiction": "cozy",
    "other": "dark",
}

_BOOKS_TAXONOMY = list(_BOOKS_RENDER_TONES.keys())

# Every source plugin that exists in backend/app/sources/ today. Only
# `nyt` is wired into the runtime by default (settings.sources_enabled);
# the rest are stubs ready to enable.
_BOOKS_SOURCES = [
    {"plugin_slug": "nyt", "config": {}},
    {"plugin_slug": "goodreads", "config": {}},
    {"plugin_slug": "amazon_movers", "config": {}},
    {"plugin_slug": "reddit_trends", "config": {}},
    {"plugin_slug": "booktok", "config": {}},
]

# ContentPackage.affiliate_amazon / affiliate_bookshop are still real
# columns at this revision. B3 collapses them into a JSON cta_links
# blob that reads its schema from here.
_BOOKS_CTA_FIELDS = [
    {"key": "amazon_url", "label": "Amazon"},
    {"key": "bookshop_url", "label": "Bookshop"},
]

# B4 replaces these stubs with extracted Jinja2 templates from
# app/services/prompts/. Empty for now so the column is non-null where
# downstream code expects a dict.
_BOOKS_PROMPTS_STUB: dict = {
    "hook_system": "",
    "script_system": "",
    "scene_prompts_system": "",
    "meta_system": "",
}


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("entity_label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("sources_config", sa.JSON(), nullable=True),
        sa.Column("prompts", sa.JSON(), nullable=True),
        sa.Column("taxonomy", sa.JSON(), nullable=True),
        sa.Column("cta_fields", sa.JSON(), nullable=True),
        sa.Column("render_tones", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_profiles_slug", "profiles", ["slug"], unique=True)

    # Seed the Books profile in the same transaction so upgrades are
    # atomic — either the table exists with a workable row, or nothing.
    # Use bulk_insert so the JSON columns serialize correctly on every
    # backend (SQLite accepts raw dicts; Postgres JSON expects JSON).
    profiles_table = sa.table(
        "profiles",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("entity_label", sa.String),
        sa.column("description", sa.Text),
        sa.column("active", sa.Boolean),
        sa.column("sources_config", sa.JSON),
        sa.column("prompts", sa.JSON),
        sa.column("taxonomy", sa.JSON),
        sa.column("cta_fields", sa.JSON),
        sa.column("render_tones", sa.JSON),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    now = datetime.utcnow()
    # Pass raw Python dicts/lists — SQLAlchemy's JSON column type binds
    # them through json.dumps internally. Double-encoding via a manual
    # json.dumps here would store quoted JSON strings instead of JSON
    # objects, which every downstream JSON-column reader mis-decodes.
    op.bulk_insert(
        profiles_table,
        [
            {
                "slug": "books",
                "name": "Books",
                "entity_label": "Book",
                "description": (
                    "Book-trailer shorts generated from NYT / Goodreads / "
                    "BookTok / Amazon / Reddit discovery. The default "
                    "profile — matches the pipeline's pre-generalization "
                    "behaviour byte-for-byte."
                ),
                "active": True,
                "sources_config": _BOOKS_SOURCES,
                "prompts": _BOOKS_PROMPTS_STUB,
                "taxonomy": _BOOKS_TAXONOMY,
                "cta_fields": _BOOKS_CTA_FIELDS,
                "render_tones": _BOOKS_RENDER_TONES,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_profiles_slug", table_name="profiles")
    op.drop_table("profiles")
