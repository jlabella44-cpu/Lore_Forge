"""render metadata on content_packages

Revision ID: 0005_render_metadata
Revises: 0004_cost_records
Create Date: 2026-04-16

Snapshot of the last successful render — duration, size, a hash of the
narration text — so the UI can show render stats and detect when a package's
narration has changed since the last render ("needs re-render").
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_render_metadata"
down_revision: Union[str, None] = "0004_cost_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("content_packages") as batch:
        batch.add_column(sa.Column("rendered_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("rendered_duration_seconds", sa.Float(), nullable=True)
        )
        batch.add_column(
            sa.Column("rendered_size_bytes", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("rendered_narration_hash", sa.String(length=64), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("content_packages") as batch:
        batch.drop_column("rendered_narration_hash")
        batch.drop_column("rendered_size_bytes")
        batch.drop_column("rendered_duration_seconds")
        batch.drop_column("rendered_at")
