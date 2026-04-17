"""Tests for the format prompt registry and pipeline dispatch."""
import pytest


class TestFormatRegistry:
    def test_get_short_hook_bundle(self):
        from app.services.prompts import get_bundle

        bundle = get_bundle("short_hook")
        assert bundle.hooks is not None
        assert bundle.script.tool_name == "record_script"
        assert bundle.scene_prompts.tool_name == "record_scene_prompts"
        assert bundle.meta.tool_name == "record_meta"
        assert bundle.target_duration_sec == 90
        assert bundle.scene_count == 5
        assert len(bundle.sections) == 5

    def test_get_list_bundle(self):
        from app.services.prompts import get_bundle

        bundle = get_bundle("list")
        assert bundle.hooks is None  # List concept IS the hook
        assert bundle.script.tool_name == "record_list_script"
        assert bundle.scene_prompts.tool_name == "record_list_scene_prompts"
        assert bundle.meta.tool_name == "record_meta"
        assert bundle.target_duration_sec == 0  # Variable
        assert bundle.sections == []

    def test_unknown_format_raises(self):
        from app.services.prompts import get_bundle

        with pytest.raises(KeyError, match="Unknown video format"):
            get_bundle("nonexistent_format")


class TestVideoFormatEnum:
    def test_enum_values(self):
        from app.models.format import VideoFormat

        assert VideoFormat.SHORT_HOOK == "short_hook"
        assert VideoFormat.LIST == "list"
        assert VideoFormat.DEEP_DIVE == "deep_dive"
        assert len(VideoFormat) == 7

    def test_enum_is_str(self):
        from app.models.format import VideoFormat

        # str(Enum) should work for DB storage
        assert isinstance(VideoFormat.LIST, str)
        assert VideoFormat.LIST == "list"


class TestRendererCompositionMap:
    def test_short_hook_composition(self):
        from app.services.renderer import FORMAT_COMPOSITION

        assert FORMAT_COMPOSITION["short_hook"] == "LoreForge"

    def test_list_composition(self):
        from app.services.renderer import FORMAT_COMPOSITION

        assert FORMAT_COMPOSITION["list"] == "LoreForgeList"


class TestListSceneDurations:
    def test_proportional_split(self):
        from app.services.renderer import _list_scene_durations

        counts = [
            {"title": "intro", "words": 10},
            {"title": "Book A", "words": 30},
            {"title": "Book B", "words": 20},
            {"title": "cta", "words": 10},
        ]
        durations = _list_scene_durations(counts, 28.0, 4)
        assert len(durations) == 4
        assert abs(sum(durations) - 28.0) < 0.1
        # Book A should be the longest
        assert durations[1] > durations[2] > durations[0]

    def test_even_split_on_missing_counts(self):
        from app.services.renderer import _list_scene_durations

        durations = _list_scene_durations(None, 20.0, 4)
        assert len(durations) == 4
        assert all(abs(d - 5.0) < 0.01 for d in durations)

    def test_floor_enforced(self):
        from app.services.renderer import _list_scene_durations

        # One scene with almost no words
        counts = [
            {"title": "intro", "words": 1},
            {"title": "Book", "words": 100},
        ]
        durations = _list_scene_durations(counts, 20.0, 2)
        assert durations[0] >= 1.5  # Floor enforced
