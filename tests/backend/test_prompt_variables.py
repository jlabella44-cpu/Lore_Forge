"""Migration 0015 turns Books prompts into Jinja templates.

Rendering each template with the Books `prompt_variables` dict must
reproduce the pre-0015 strings byte-for-byte — that's the contract
that makes #2 a zero-behavior-change commit. If this test starts
failing, either the migration's substitutions drifted or the llm.py
constants changed without a follow-up to the migration.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.profile import Profile
from app.services import llm, prompt_renderer
from app.services.prompts import short_hook


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_alembic_to_head(db_file: Path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_file}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT / "db"),
        env=env,
        check=True,
        capture_output=True,
    )


def test_books_prompts_render_identically_to_pre_0015_text(tmp_path):
    """For every stage, rendering the post-0015 template with the
    post-0014 Books `prompt_variables` returns exactly the string
    that was seeded by 0012 + 0013."""
    db_file = tmp_path / "pv.sqlite"
    _run_alembic_to_head(db_file)

    engine = create_engine(f"sqlite:///{db_file}")
    try:
        with sessionmaker(bind=engine)() as s:
            books = s.query(Profile).filter(Profile.slug == "books").one()

            # 0014 seeded these exact variables.
            assert books.prompt_variables == {
                "entity_type": "book",
                "audience_noun": "readers",
                "platform_tag": "BookTok",
                "review_site": "Goodreads",
            }

            # Pre-0015 text — same constants the snapshot test in B4
            # verified after 0013. Re-referenced here so a future
            # edit to those constants triggers *this* test first.
            pre_0015 = {
                "hook_system": short_hook.HOOKS_SYSTEM,
                "script_system": short_hook.SCRIPT_SYSTEM,
                "scene_prompts_system": llm._SCENE_PROMPTS_SYSTEM,
                "meta_system": short_hook.META_SYSTEM,
            }

            for stage, expected in pre_0015.items():
                template = books.prompts[stage]
                # Sanity: the post-0015 template really did gain Jinja
                # variables. If a stage stopped parameterizing, the
                # test should still pass but we'd lose coverage.
                if stage != "scene_prompts_system":
                    assert "{{" in template, f"{stage} has no Jinja vars"

                rendered = prompt_renderer.render(template, books.prompt_variables)
                assert rendered == expected, (
                    f"{stage}: rendered template doesn't match pre-0015 text"
                )
    finally:
        engine.dispose()


def test_swap_variables_produces_different_output(tmp_path):
    """Flip the variables to Films values → rendered text actually
    uses those tokens. Proves the templates are really parameterized
    (not just identity strings)."""
    db_file = tmp_path / "pv2.sqlite"
    _run_alembic_to_head(db_file)

    engine = create_engine(f"sqlite:///{db_file}")
    try:
        with sessionmaker(bind=engine)() as s:
            books = s.query(Profile).filter(Profile.slug == "books").one()
            films_vars = {
                "entity_type": "film",
                "audience_noun": "viewers",
                "platform_tag": "FilmTok",
                "review_site": "IMDb",
            }

            hook_rendered = prompt_renderer.render(
                books.prompts["hook_system"], films_vars
            )
            assert "film trailer videos" in hook_rendered
            assert "book trailer videos" not in hook_rendered

            script_rendered = prompt_renderer.render(
                books.prompts["script_system"], films_vars
            )
            assert "viewers can't put the film down" in script_rendered
            assert "FilmTok views" in script_rendered
            assert "IMDb rating" in script_rendered

            meta_rendered = prompt_renderer.render(
                books.prompts["meta_system"], films_vars
            )
            assert "film trailer script" in meta_rendered
            assert "film's genre" in meta_rendered
    finally:
        engine.dispose()
