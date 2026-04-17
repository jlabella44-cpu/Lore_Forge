"""image_asset_cache for prompt-level image dedup

Revision ID: 0007_image_asset_cache
Revises: 0006_series_and_formats
Create Date: 2026-04-17

Content-addressed cache of generated images keyed by
(provider, model, aspect, prompt). On cache hit the renderer copies the
cached blob into the per-package work_dir instead of issuing a new
provider API call — so failed/rerun jobs no longer pay twice for the same
prompt. Pruning is by `last_used_at` (LRU) so hot scenes survive.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_image_asset_cache"
down_revision: Union[str, None] = "0006_series_and_formats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_asset_cache",
        sa.Column("prompt_hash", sa.String(length=64), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("aspect", sa.String(length=8), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "bytes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column(
            "hit_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_image_asset_cache_last_used_at",
        "image_asset_cache",
        ["last_used_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_image_asset_cache_last_used_at", table_name="image_asset_cache"
    )
    op.drop_table("image_asset_cache")
