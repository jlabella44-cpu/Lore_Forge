"""Unit tests for services/llm.py — provider dispatch + script parsing."""
from unittest.mock import MagicMock, patch

import pytest

from app.services import llm


# --- script_by_section ------------------------------------------------------


def test_script_by_section_splits_on_markdown_headers():
    script = (
        "## HOOK\nIntrigue line.\n\n"
        "## WORLD TEASE\nA cursed forest.\n\n"
        "## EMOTIONAL PULL\nYou can't look away.\n\n"
        "## SOCIAL PROOF\n#1 NYT.\n\n"
        "## CTA\nLink in bio."
    )
    out = llm.script_by_section(script)
    assert out["hook"] == "Intrigue line."
    assert out["world_tease"] == "A cursed forest."
    assert out["emotional_pull"] == "You can't look away."
    assert out["social_proof"] == "#1 NYT."
    assert out["cta"] == "Link in bio."


def test_script_by_section_tolerates_header_variations():
    """Lenient on casing, header depth, and trailing colons."""
    script = (
        "# Hook:\nA sentence.\n"
        "### world tease\nAnother line.\n"
        "## EMOTIONAL PULL\nx\n"
        "## Social Proof\ny\n"
        "## cta\nz\n"
    )
    out = llm.script_by_section(script)
    assert out["hook"] == "A sentence."
    assert out["world_tease"] == "Another line."
    assert out["emotional_pull"] == "x"
    assert out["social_proof"] == "y"
    assert out["cta"] == "z"


def test_script_by_section_missing_sections_return_empty():
    """A script missing some sections returns empty strings — never raises."""
    out = llm.script_by_section("## HOOK\nonly a hook")
    assert out["hook"] == "only a hook"
    assert out["world_tease"] == ""
    assert out["emotional_pull"] == ""
    assert out["social_proof"] == ""
    assert out["cta"] == ""


def test_script_by_section_handles_empty_input():
    out = llm.script_by_section("")
    assert all(v == "" for v in out.values())
    assert set(out) == set(llm.SECTIONS)


# --- dispatch: hooks -------------------------------------------------------


@pytest.fixture
def settings_with_keys(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "dashscope_api_key", "sk-ds-test")
    monkeypatch.setattr(settings, "script_provider", "claude")
    monkeypatch.setattr(settings, "meta_provider", "qwen")
    llm._anthropic_client.cache_clear()
    llm._openai_client.cache_clear()
    llm._qwen_client.cache_clear()


def _claude_tool_response(input_dict):
    """Build a fake Anthropic Messages response that emits a tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = input_dict
    resp = MagicMock()
    resp.content = [block]
    return resp


def test_generate_hooks_routes_to_claude_with_cached_system(settings_with_keys):
    fake = {
        "alternatives": [
            {"angle": "curiosity", "text": "a"},
            {"angle": "fear", "text": "b"},
            {"angle": "promise", "text": "c"},
        ],
        "chosen_index": 1,
        "rationale": "fear wins",
    }
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        out = llm.generate_hooks(
            title="X", author="Y", description="Z", genre="fantasy"
        )

    assert out["alternatives"] == fake["alternatives"]
    assert out["chosen_index"] == 1

    kwargs = c.return_value.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_hooks"}
    # Prompt caching is on so Claude can reuse the stable system prompt
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["model"] == "claude-opus-4-6"


def test_generate_hooks_clamps_out_of_range_chosen_index(settings_with_keys):
    """If the model hallucinates chosen_index=5, clamp to 0..2."""
    fake = {
        "alternatives": [
            {"angle": "curiosity", "text": "a"},
            {"angle": "fear", "text": "b"},
            {"angle": "promise", "text": "c"},
        ],
        "chosen_index": 5,
        "rationale": "",
    }
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        out = llm.generate_hooks(
            title="X", author="Y", description=None, genre="fantasy"
        )
    assert 0 <= out["chosen_index"] <= 2


def test_generate_script_threads_hook_and_note_into_user(settings_with_keys):
    fake = {
        "script": "## HOOK\nhook\n\n## WORLD TEASE\nw\n\n## EMOTIONAL PULL\ne\n\n## SOCIAL PROOF\ns\n\n## CTA\nc",
        "narration": "hook w e s c",
        "section_word_counts": {
            "hook": 1, "world_tease": 1, "emotional_pull": 1,
            "social_proof": 1, "cta": 1,
        },
    }
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        llm.generate_script(
            title="T",
            author="A",
            description="D",
            genre="thriller",
            chosen_hook="THE CHOSEN HOOK",
            note="darker please",
        )

    user = c.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "THE CHOSEN HOOK" in user
    assert "darker please" in user


def test_generate_scene_prompts_feeds_parsed_sections(settings_with_keys):
    fake = {
        "scenes": [
            {"section": s, "prompt": f"p_{s}", "focus": "f"}
            for s in llm.SECTIONS
        ]
    }
    script = (
        "## HOOK\nH\n\n## WORLD TEASE\nW\n\n## EMOTIONAL PULL\nE\n\n"
        "## SOCIAL PROOF\nS\n\n## CTA\nC"
    )
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        out = llm.generate_scene_prompts(script=script, genre="fantasy")

    assert [s["section"] for s in out["scenes"]] == list(llm.SECTIONS)

    # The user message includes each section's content, tagged with its name
    user = c.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
    for section in llm.SECTIONS:
        assert f"[{section.upper()}]" in user


# --- dispatch: dossier threading ------------------------------------------


_SAMPLE_DOSSIER = {
    "setting": {"name": "bioluminescent coral ruins", "era": "far future", "atmosphere": "eerie hush"},
    "protagonist_sketch": "a marine biologist haunted by loss",
    "central_conflict": "recovering a vanished research crew",
    "themes_tropes": ["climate grief", "found family"],
    "visual_motifs": [
        "glowing coral lattice",
        "abandoned submersible",
        "faded crew photograph",
    ],
    "tonal_keywords": ["haunting", "chrome-lit"],
    "comparable_titles": ["Annihilation"],
    "reader_reactions": ["I couldn't stop thinking about it"],
    "content_hooks": ["the coral remembers"],
    "signature_images": ["a lantern in deep water"],
}


def _last_user_content(mock_client) -> str:
    return mock_client.return_value.messages.create.call_args.kwargs[
        "messages"
    ][0]["content"]


def test_generate_hooks_threads_dossier_into_user(settings_with_keys):
    fake = {
        "alternatives": [
            {"angle": "curiosity", "text": "a"},
            {"angle": "fear", "text": "b"},
            {"angle": "promise", "text": "c"},
        ],
        "chosen_index": 0,
        "rationale": "",
    }
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        llm.generate_hooks(
            title="T", author="A", description="D", genre="scifi",
            dossier=_SAMPLE_DOSSIER,
        )

    user = _last_user_content(c)
    assert "visual_motifs" in user
    assert "glowing coral lattice" in user


def test_generate_script_threads_dossier_into_user(settings_with_keys):
    fake = {
        "script": "## HOOK\nh\n\n## WORLD TEASE\nw\n\n## EMOTIONAL PULL\ne\n\n## SOCIAL PROOF\ns\n\n## CTA\nc",
        "narration": "n",
        "section_word_counts": {
            "hook": 1, "world_tease": 1, "emotional_pull": 1,
            "social_proof": 1, "cta": 1,
        },
    }
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        llm.generate_script(
            title="T", author="A", description="D", genre="scifi",
            chosen_hook="HOOK", dossier=_SAMPLE_DOSSIER,
        )

    user = _last_user_content(c)
    assert "visual_motifs" in user
    assert "abandoned submersible" in user


def test_generate_scene_prompts_threads_dossier_into_user(settings_with_keys):
    fake = {
        "scenes": [
            {"section": s, "prompt": f"p_{s}", "focus": "f"}
            for s in llm.SECTIONS
        ]
    }
    script = (
        "## HOOK\nH\n\n## WORLD TEASE\nW\n\n## EMOTIONAL PULL\nE\n\n"
        "## SOCIAL PROOF\nS\n\n## CTA\nC"
    )
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        llm.generate_scene_prompts(
            script=script, genre="scifi", dossier=_SAMPLE_DOSSIER,
        )

    user = _last_user_content(c)
    assert "visual_motifs" in user
    assert "glowing coral lattice" in user


def test_creative_stages_omit_dossier_block_when_none(settings_with_keys):
    """Legacy callers passing no dossier should not inject a block."""
    fake = {
        "alternatives": [
            {"angle": "curiosity", "text": "a"},
            {"angle": "fear", "text": "b"},
            {"angle": "promise", "text": "c"},
        ],
        "chosen_index": 0,
        "rationale": "",
    }
    with patch.object(llm, "_anthropic_client") as c:
        c.return_value.messages.create.return_value = _claude_tool_response(fake)
        llm.generate_hooks(title="T", author="A", description="D", genre="scifi")

    user = _last_user_content(c)
    assert "visual_motifs" not in user


# --- dispatch: meta (Qwen / OpenAI-compatible path) ------------------------


def test_classify_genre_routes_to_qwen_with_json_mode(settings_with_keys):
    """META_PROVIDER defaults to Qwen; uses OpenAI-compatible json_object."""
    import json

    fake_choice = MagicMock()
    fake_choice.message.content = json.dumps({"genre": "scifi", "confidence": 0.88})
    fake_resp = MagicMock()
    fake_resp.choices = [fake_choice]

    with patch.object(llm, "_qwen_client") as c:
        c.return_value.chat.completions.create.return_value = fake_resp
        genre, conf = llm.classify_genre("Dune", "Herbert", "A desert prophecy.")

    assert genre == "scifi"
    assert conf == 0.88

    kwargs = c.return_value.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "qwen-plus" in kwargs["model"]
