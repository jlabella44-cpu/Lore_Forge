"""Tests for backend/app/services/quality_gate.py and its wiring into the
short-hook pipeline."""
from unittest.mock import patch

import pytest

from app.services import quality_gate


_DOSSIER = {
    "visual_motifs": [
        "glowing coral lattice",
        "abandoned submersible",
        "faded crew photograph",
    ],
}


# --- unit: check_script ----------------------------------------------------


def test_check_script_passes_on_clean_script_with_motif():
    script = (
        "## HOOK\nThe glowing coral lattice remembers.\n\n"
        "## WORLD TEASE\nA drowned city.\n"
    )
    assert quality_gate.check_script(script, _DOSSIER) == []


def test_check_script_flags_banned_vocab():
    script = (
        "## HOOK\nAn unputdownable thriller.\n"
        "It's page-turning and captivating. "
        "Also: a glowing coral lattice."
    )
    reasons = quality_gate.check_script(script, _DOSSIER)
    assert len(reasons) == 1
    assert "unputdownable" in reasons[0]
    assert "page-turning" in reasons[0]
    assert "captivating" in reasons[0]


def test_check_script_flags_missing_motif():
    script = "## HOOK\nA perfectly fine hook with no motif citations.\n"
    reasons = quality_gate.check_script(script, _DOSSIER)
    assert len(reasons) == 1
    assert "visual motif" in reasons[0].lower()


def test_check_script_reports_both_failures_when_both_present():
    script = "A stunning read with no motif."
    reasons = quality_gate.check_script(script, _DOSSIER)
    assert len(reasons) == 2


def test_check_script_no_dossier_skips_motif_check():
    """No dossier → motif gate can't fire, only banned vocab matters."""
    assert quality_gate.check_script("normal script", None) == []
    reasons = quality_gate.check_script("unputdownable", None)
    assert len(reasons) == 1
    assert "unputdownable" in reasons[0]


def test_banned_vocab_respects_word_boundaries():
    """'captivatingly' must not trip the 'captivating' rule."""
    script = "The prose was captivatingly strange. glowing coral lattice."
    assert quality_gate.check_script(script, _DOSSIER) == []


def test_motif_match_is_case_insensitive():
    script = "## HOOK\nThe GLOWING CORAL LATTICE remembers.\n"
    assert quality_gate.check_script(script, _DOSSIER) == []


def test_feedback_note_preserves_prior_note():
    note = quality_gate.feedback_note(["do A", "do B"], "darker please")
    assert "darker please" in note
    assert "do A" in note
    assert "do B" in note


# --- pipeline wiring -------------------------------------------------------


NYT_ONE = [
    {
        "title": "The Deep Sky",
        "author": "Yume Kitasei",
        "isbn": "9781250875334",
        "description": "A sci-fi thriller.",
        "cover_url": None,
        "source_rank": 1,
    }
]

_PIPELINE_DOSSIER = {
    "setting": {"name": "", "era": "", "atmosphere": ""},
    "visual_motifs": ["glowing coral lattice"],
}

_BAD_SCRIPT = {
    "script": (
        "## HOOK\nAn unputdownable ride.\n\n"
        "## WORLD TEASE\nw\n\n"
        "## EMOTIONAL PULL\ne\n\n"
        "## SOCIAL PROOF\ns\n\n"
        "## CTA\nc"
    ),
    "narration": "n",
    "section_word_counts": {
        "hook": 1, "world_tease": 1, "emotional_pull": 1,
        "social_proof": 1, "cta": 1,
    },
}

_GOOD_SCRIPT = {
    "script": (
        "## HOOK\nThe glowing coral lattice remembers.\n\n"
        "## WORLD TEASE\nw\n\n"
        "## EMOTIONAL PULL\ne\n\n"
        "## SOCIAL PROOF\ns\n\n"
        "## CTA\nc"
    ),
    "narration": "n",
    "section_word_counts": {
        "hook": 1, "world_tease": 1, "emotional_pull": 1,
        "social_proof": 1, "cta": 1,
    },
}

_FAKE_HOOKS = {
    "alternatives": [
        {"angle": "curiosity", "text": "a"},
        {"angle": "fear", "text": "b"},
        {"angle": "promise", "text": "c"},
    ],
    "chosen_index": 0,
    "rationale": "",
}

_FAKE_SCENES = {
    "scenes": [
        {"section": s, "prompt": f"p_{s}", "focus": "f"}
        for s in ["hook", "world_tease", "emotional_pull", "social_proof", "cta"]
    ],
}

_FAKE_META = {
    "titles": {"tiktok": "t", "yt_shorts": "t", "ig_reels": "t", "threads": "t"},
    "hashtags": {"tiktok": [], "yt_shorts": [], "ig_reels": [], "threads": []},
}


@pytest.fixture
def book_id(client):
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_ONE),
        patch("app.services.llm.classify_genre", return_value=("scifi", 0.9)),
    ):
        client.post("/discover/run")
    return client.get("/books").json()[0]["id"]


@pytest.fixture
def quality_gate_on(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "quality_gate", True)


def test_pipeline_regenerates_script_when_gate_fails(
    client, book_id, quality_gate_on
):
    """First script has banned vocab → gate triggers a regen; second script
    is accepted and shipped."""
    with (
        patch(
            "app.services.llm.generate_book_dossier",
            return_value=_PIPELINE_DOSSIER,
        ),
        patch("app.services.llm.generate_hooks", return_value=_FAKE_HOOKS),
        patch(
            "app.services.llm.generate_script",
            side_effect=[_BAD_SCRIPT, _GOOD_SCRIPT],
        ) as script_mock,
        patch("app.services.llm.generate_scene_prompts", return_value=_FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=_FAKE_META),
    ):
        res = client.post(f"/books/{book_id}/generate", json={})

    assert res.status_code == 200
    # Gate regenerated exactly once.
    assert script_mock.call_count == 2

    # The retry carried quality feedback into the note kwarg.
    retry_note = script_mock.call_args_list[1].kwargs["note"]
    assert "Quality feedback" in retry_note
    assert "unputdownable" in retry_note

    # The shipped script is the clean one.
    pkg = client.get(f"/books/{book_id}").json()["packages"][0]
    assert "glowing coral lattice" in pkg["script"]


def test_pipeline_skips_gate_when_flag_off(client, book_id):
    """Gate off: bad script is shipped without retry."""
    with (
        patch(
            "app.services.llm.generate_book_dossier",
            return_value=_PIPELINE_DOSSIER,
        ),
        patch("app.services.llm.generate_hooks", return_value=_FAKE_HOOKS),
        patch(
            "app.services.llm.generate_script",
            return_value=_BAD_SCRIPT,
        ) as script_mock,
        patch("app.services.llm.generate_scene_prompts", return_value=_FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=_FAKE_META),
    ):
        client.post(f"/books/{book_id}/generate", json={})

    assert script_mock.call_count == 1


def test_pipeline_passes_gate_on_first_try_does_not_regen(
    client, book_id, quality_gate_on
):
    with (
        patch(
            "app.services.llm.generate_book_dossier",
            return_value=_PIPELINE_DOSSIER,
        ),
        patch("app.services.llm.generate_hooks", return_value=_FAKE_HOOKS),
        patch(
            "app.services.llm.generate_script",
            return_value=_GOOD_SCRIPT,
        ) as script_mock,
        patch("app.services.llm.generate_scene_prompts", return_value=_FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=_FAKE_META),
    ):
        client.post(f"/books/{book_id}/generate", json={})

    assert script_mock.call_count == 1
