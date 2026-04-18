"""profiles.prompt_variables: Jinja variable dict per profile

Revision ID: 0014_prompt_variables
Revises: 0013_reconcile_scene_prompts
Create Date: 2026-04-18

Adds a new JSON column on `profiles` that holds the substitution
dict passed to `prompt_renderer.render(template, variables)` for
every LLM stage. Each profile ships its own flat map of
`{variable_name: value}` pairs — `{"entity_type": "book"}` for
Books, `{"entity_type": "film"}` for a Movies profile, etc.

Seeds the Books profile with the four variables the next migration
(0015) will thread into the prompt templates:

  entity_type   → "book"
  audience_noun → "readers"
  platform_tag  → "BookTok"
  review_site   → "Goodreads"

This migration only adds the column and backfills Books. 0015 is
what actually injects the `{{...}}` placeholders into the prompts.
Splitting the two lets an operator roll back the prompt change
without losing the column if they edited other variables in the UI.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_prompt_variables"
down_revision: Union[str, None] = "0013_reconcile_scene_prompts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BOOKS_VARS = {
    "entity_type": "book",
    "audience_noun": "readers",
    "platform_tag": "BookTok",
    "review_site": "Goodreads",
}


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("prompt_variables", sa.JSON(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE profiles SET prompt_variables = :v WHERE slug = 'books'"
        ).bindparams(v=json.dumps(_BOOKS_VARS))
    )


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("prompt_variables")
