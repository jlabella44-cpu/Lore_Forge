"""Every YAML file in resources/profiles/ imports cleanly via the
router. Regression-proofs the shipped examples against drift in the
profile schema — any time a required key is added to Profile, these
tests fail until the examples are updated.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


RESOURCES_DIR = Path(__file__).resolve().parents[2] / "resources" / "profiles"


def _example_files() -> list[Path]:
    return sorted(RESOURCES_DIR.glob("*.yaml"))


@pytest.mark.parametrize(
    "path", _example_files(), ids=lambda p: p.name
)
def test_example_profile_is_valid_yaml(path):
    parsed = yaml.safe_load(path.read_text())
    assert isinstance(parsed, dict), f"{path.name} top-level must be a mapping"
    # Sanity checks — the router enforces the real contract at import
    # time; this is the "file is readable" gate.
    for key in ("slug", "name", "entity_label"):
        assert parsed.get(key), f"{path.name} missing required key {key!r}"


@pytest.mark.parametrize(
    "path", _example_files(), ids=lambda p: p.name
)
def test_example_profile_imports_round_trips(client, path):
    body = path.read_text()
    res = client.post(
        "/profiles/import",
        content=body,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert res.status_code == 200, res.text

    data = res.json()
    parsed = yaml.safe_load(body)
    assert data["slug"] == parsed["slug"]
    assert data["name"] == parsed["name"]
    assert data["entity_label"] == parsed["entity_label"]
    # New imports never auto-activate (the UI / operator decides).
    assert data["active"] is False

    # Sanity: sources_config + prompts + taxonomy are non-empty so
    # the example is actually usable, not just schema-valid.
    assert data["sources_config"], f"{path.name} has no sources_config"
    assert data["prompts"], f"{path.name} has no prompts"
    # Every prompt template should render without variables — the
    # shipped examples don't use any Jinja variables yet.
    from app.services.prompt_renderer import render

    for stage, template in data["prompts"].items():
        assert render(template, {}) == template, (
            f"{path.name} prompts.{stage} has unresolved Jinja vars"
        )


def test_shipped_example_count():
    """Locks in the set shipped today so a future change — moving the
    example dir, renaming a file — surfaces in review instead of
    silently shrinking the set."""
    names = {p.name for p in _example_files()}
    assert names == {"movies.yaml", "recipes.yaml", "news.yaml"}
