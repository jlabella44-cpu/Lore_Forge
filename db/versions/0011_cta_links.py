"""cta_links: collapse affiliate_amazon/affiliate_bookshop into JSON

Revision ID: 0011_cta_links
Revises: 0010_content_items
Create Date: 2026-04-18

Phase B3 of the generalization plan. Book-specific `affiliate_amazon`
and `affiliate_bookshop` columns on `content_packages` collapse into a
single `cta_links` JSON blob keyed by whatever the active profile's
`cta_fields` schema declares. For Books this means
`{"amazon_url": ..., "bookshop_url": ...}`; a Films profile might use
`{"trailer_url": ..., "streaming_url": ...}` — same column, different
keys.

Existing rows are migrated non-destructively: any non-null affiliate_*
value lands in `cta_links` under the Books-profile key before the
columns drop.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_cta_links"
down_revision: Union[str, None] = "0010_content_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("content_packages") as batch:
        batch.add_column(sa.Column("cta_links", sa.JSON(), nullable=True))

    # Copy surviving affiliate links into the new JSON column before the
    # source columns drop. NULL → NULL (no CTA); partials land as
    # `{"amazon_url": "..."}` with the other key omitted.
    rows = conn.execute(
        sa.text(
            "SELECT id, affiliate_amazon, affiliate_bookshop "
            "FROM content_packages"
        )
    ).fetchall()
    for row in rows:
        links = {}
        if row.affiliate_amazon:
            links["amazon_url"] = row.affiliate_amazon
        if row.affiliate_bookshop:
            links["bookshop_url"] = row.affiliate_bookshop
        if not links:
            continue
        conn.execute(
            sa.text(
                "UPDATE content_packages SET cta_links = :c WHERE id = :i"
            ).bindparams(c=json.dumps(links), i=row.id)
        )

    with op.batch_alter_table("content_packages") as batch:
        batch.drop_column("affiliate_amazon")
        batch.drop_column("affiliate_bookshop")


def downgrade() -> None:
    # Lossy — new CTA keys added after upgrade won't round-trip through
    # the two legacy columns. Restore from backup instead.
    raise NotImplementedError(
        "downgrade from 0011 is lossy; restore from backup instead"
    )
