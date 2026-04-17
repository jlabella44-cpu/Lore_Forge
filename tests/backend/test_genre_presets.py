"""Unit tests for backend/app/services/genre_presets.py and its wiring
into generate_scene_prompts."""
from unittest.mock import MagicMock, patch

import pytest

from app.services import genre_presets, llm


# --- unit ------------------------------------------------------------------


@pytest.mark.parametrize(
    "genre", list(genre_presets.GENRE_PRESETS.keys()),
)
def test_every_preset_has_all_fields(genre):
    preset = genre_presets.GENRE_PRESETS[genre]
    assert preset["palette"]
    assert preset["lens"]
    assert preset["lighting"]
    assert preset["composition"]


def test_get_returns_preset_for_known_genre():
    preset = genre_presets.get("thriller")
    assert preset is not None
    assert "bruise blue" in preset["palette"]


def test_get_returns_none_for_unknown_genre():
    assert genre_presets.get("other") is None
    assert genre_presets.get("cookbook") is None
    assert genre_presets.get(None) is None
    assert genre_presets.get("") is None


def test_get_is_case_insensitive():
    assert genre_presets.get("THRILLER") == genre_presets.get("thriller")


def test_preset_block_empty_when_unknown():
    assert genre_presets.preset_block("other") == ""
    assert genre_presets.preset_block(None) == ""


def test_preset_block_contains_all_four_defaults():
    block = genre_presets.preset_block("fantasy")
    assert "Visual preset" in block
    assert "palette:" in block
    assert "lens:" in block
    assert "lighting:" in block
    assert "composition:" in block
    assert "gold leaf" in block  # one of the fantasy palette entries


# --- wiring into generate_scene_prompts ------------------------------------


@pytest.fixture
def settings_with_keys(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "script_provider", "claude")
    llm._anthropic_client.cache_clear()


def _claude_tool_response(input_dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = input_dict
    resp = MagicMock()
    resp.content = [block]
    return resp


def _fake_scene_response():
    return _claude_tool_response(
        {
            "scenes": [
                {"section": s, "prompt": f"p_{s}", "focus": "f"}
                for s in llm.SECTIONS
            ]
        }
    )


SCRIPT = (
    "## HOOK\nH\n\n## WORLD TEASE\nW\n\n## EMOTIONAL PULL\nE\n\n"
    "## SOCIAL PROOF\nS\n\n## CTA\nC"
)


def _last_user(mock_client):
    return mock_client.return_value.messages.create.call_args.kwargs[
        "messages"
    ][0]["content"]


def test_scene_prompts_injects_preset_block_for_known_genre(settings_with_keys):
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _fake_scene_response()
        llm.generate_scene_prompts(script=SCRIPT, genre="scifi")

    user = _last_user(c)
    assert "Visual preset" in user
    assert "chrome white" in user  # scifi palette


def test_scene_prompts_omits_preset_block_for_unknown_genre(settings_with_keys):
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _fake_scene_response()
        llm.generate_scene_prompts(script=SCRIPT, genre="other")

    user = _last_user(c)
    assert "Visual preset" not in user


def test_scene_prompts_coexists_with_dossier_block(settings_with_keys):
    """Dossier block and preset block both land in the user message; the
    order is dossier → preset so dossier reads first."""
    dossier = {
        "visual_motifs": ["glowing coral lattice"],
        "setting": {"name": "drowned city"},
    }
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _fake_scene_response()
        llm.generate_scene_prompts(
            script=SCRIPT, genre="horror", dossier=dossier,
        )

    user = _last_user(c)
    assert "glowing coral lattice" in user
    assert "Visual preset" in user
    assert user.index("glowing coral lattice") < user.index("Visual preset")
