"""python -m app.profile_cli — each subcommand against a test DB."""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
import yaml


def _run(argv: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    """Invoke the CLI's main() and capture stdout/stderr."""
    from app import profile_cli

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = profile_cli.main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if exc.code is not None else 0
    return rc, out.getvalue(), err.getvalue()


@pytest.fixture(autouse=True)
def _seed(client):
    """`client` brings up the conftest fixtures which swap
    db_module.SessionLocal → the in-memory test engine and seed the
    Books profile. The CLI uses `from app.db import SessionLocal`;
    because profile_cli is imported inside _run (not at module load),
    it re-reads the swapped module attribute."""
    yield


def test_list_shows_seeded_books():
    rc, out, err = _run(["list"])
    assert rc == 0, err
    assert "books" in out
    assert "*" in out  # active marker


def test_show_emits_json():
    rc, out, err = _run(["show", "books"])
    assert rc == 0, err
    data = json.loads(out)
    assert data["slug"] == "books"
    assert data["entity_label"] == "Book"


def test_show_missing_profile_exits_1():
    rc, _out, err = _run(["show", "nope"])
    assert rc == 1
    assert "not found" in err


def test_export_produces_parseable_yaml():
    rc, out, err = _run(["export", "books"])
    assert rc == 0, err
    parsed = yaml.safe_load(out)
    assert parsed["slug"] == "books"
    # Volatile fields stripped — same contract as the HTTP export.
    assert "active" not in parsed
    assert "id" not in parsed


def test_import_from_file(tmp_path):
    payload = yaml.safe_dump(
        {"slug": "films", "name": "Films", "entity_label": "Film"}
    )
    path = tmp_path / "films.yaml"
    path.write_text(payload)

    rc, out, err = _run(["import", str(path)])
    assert rc == 0, err
    assert "films" in out

    # Confirm it landed.
    rc, out, _ = _run(["show", "films"])
    assert rc == 0


def test_import_rejects_existing_without_overwrite(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text(
        yaml.safe_dump({"slug": "books", "name": "dup", "entity_label": "Book"})
    )
    rc, _out, err = _run(["import", str(path)])
    assert rc == 1
    assert "exists" in err


def test_import_overwrite_replaces(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "slug": "books",
                "name": "Reimported",
                "entity_label": "Book",
                "description": "from the CLI",
            }
        )
    )
    rc, _out, err = _run(["import", str(path), "--overwrite"])
    assert rc == 0, err

    rc, out, _ = _run(["show", "books"])
    assert json.loads(out)["name"] == "Reimported"


def test_import_bundle_loads_examples():
    rc, out, err = _run(["import-bundle"])
    assert rc == 0, err
    for expected in ("movies", "recipes", "news"):
        assert expected in out, f"{expected} missing from bundle import stdout"


def test_activate_flips_active_flag(tmp_path):
    # Import films first so there's something to activate.
    path = tmp_path / "films.yaml"
    path.write_text(
        yaml.safe_dump({"slug": "films", "name": "Films", "entity_label": "Film"})
    )
    _run(["import", str(path)])

    rc, _out, err = _run(["activate", "films"])
    assert rc == 0, err

    rc, list_out, _ = _run(["list"])
    # `*` should appear on the `films` row now, not on books.
    films_row = [ln for ln in list_out.splitlines() if "films" in ln][0]
    books_row = [ln for ln in list_out.splitlines() if " books " in ln][0]
    assert films_row.startswith(" *")
    assert books_row.startswith("  ")


def test_delete_refuses_active():
    rc, _out, err = _run(["delete", "books"])
    assert rc == 1
    assert "active" in err.lower()


def test_delete_removes_unused(tmp_path):
    path = tmp_path / "films.yaml"
    path.write_text(
        yaml.safe_dump({"slug": "films", "name": "Films", "entity_label": "Film"})
    )
    _run(["import", str(path)])

    rc, _out, err = _run(["delete", "films"])
    assert rc == 0, err

    rc, _out, _ = _run(["show", "films"])
    assert rc == 1  # gone


def test_vars_merges_into_prompt_variables():
    rc, out, err = _run(
        ["vars", "books", "entity_type=book", "audience_noun=readers"]
    )
    assert rc == 0, err
    data = json.loads(out)
    assert data["entity_type"] == "book"
    assert data["audience_noun"] == "readers"


def test_vars_rejects_malformed_pair():
    rc, _out, err = _run(["vars", "books", "not-a-kv-pair"])
    assert rc == 1
    assert "expected key=value" in err
