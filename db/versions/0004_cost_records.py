"""cost_records: per-call spend tracking

Revision ID: 0004_cost_records
Revises: 0003_jobs
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_cost_records"
down_revision: Union[str, None] = "0003_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cost_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("call_name", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("units", sa.Float(), nullable=True),
        sa.Column("estimated_cents", sa.Float(), nullable=False, server_default="0"),
        sa.Column("package_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["content_packages.id"]),
    )
    op.create_index(
        "ix_cost_records_created_at", "cost_records", ["created_at"]
    )
    op.create_index(
        "ix_cost_records_package_id", "cost_records", ["package_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_cost_records_package_id", table_name="cost_records")
    op.drop_index("ix_cost_records_created_at", table_name="cost_records")
    op.drop_table("cost_records")
