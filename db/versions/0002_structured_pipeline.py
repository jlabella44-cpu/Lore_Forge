"""structured pipeline: hook portfolio, section-anchored prompts, captions

Revision ID: 0002_structured_pipeline
Revises: 0001_initial
Create Date: 2026-04-15

Adds four new jsonb/int columns to content_packages. No existing column
shape changes — old rows still work, they just have NULL in the new fields.
The `visual_prompts` column keeps its JSON type; the shape inside evolves
from list[str] (Phase 1) to list[{section, prompt, focus}] (Phase 2+).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_structured_pipeline"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("content_packages") as batch:
        batch.add_column(sa.Column("hook_alternatives", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("chosen_hook_index", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("section_word_counts", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("captions", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content_packages") as batch:
        batch.drop_column("captions")
        batch.drop_column("section_word_counts")
        batch.drop_column("chosen_hook_index")
        batch.drop_column("hook_alternatives")
