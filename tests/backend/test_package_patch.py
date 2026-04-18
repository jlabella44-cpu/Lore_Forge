"""PATCH /packages/{package_id} — hand-edit generated creative fields."""
from unittest.mock import patch

import pytest


NYT_ONE = [
    {
        "title": "The Ghost Orchid",
        "author": "David Baldacci",
        "isbn": "9781538765388",
        "description": "A mystery.",
        "cover_url": None,
        "source_rank": 1,
    }
]

FAKE_HOOKS = {
    "alternatives": [
        {"angle": "curiosity", "text": "What happens when the orchid blooms?"},
        {"angle": "fear", "text": "One flower. Seven dead witnesses."},
        {"angle": "promise", "text": "If you loved Gone Girl, this is next."},
    ],
    "chosen_index": 1,
    "rationale": "",
}

FAKE_SCRIPT = {
    "script": (
        "## HOOK\nOne flower. Seven dead witnesses.\n\n"
        "## WORLD TEASE\nA swamp-town mystery.\n\n"
        "## EMOTIONAL PULL\nYou won't look away.\n\n"
        "## SOCIAL PROOF\n#1 NYT bestseller.\n\n"
        "## CTA\nLink in bio to grab it."
    ),
    "narration": "One flower. Seven dead witnesses.",
    "section_word_counts": {
        "hook": 4, "world_tease": 4, "emotional_pull": 4,
        "social_proof": 4, "cta": 5,
    },
}

FAKE_SCENES = {
    "scenes": [
        {"section": s, "prompt": f"p_{s}", "focus": "f"}
        for s in ["hook", "world_tease", "emotional_pull", "social_proof", "cta"]
    ],
}

FAKE_META = {
    "titles": {
        "tiktok": "original tt title",
        "yt_shorts": "yt title",
        "ig_reels": "ig title",
        "threads": "th title",
    },
    "hashtags": {
        "tiktok": ["#booktok"],
        "yt_shorts": ["#shorts"],
        "ig_reels": ["#bookstagram"],
        "threads": ["#books"],
    },
}


@pytest.fixture
def package_id(client):
    """Generate one package and return its id."""
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_ONE),
        patch("app.services.llm.classify_genre", return_value=("thriller", 0.85)),
    ):
        client.post("/discover/run")
    book_id = client.get("/books").json()[0]["id"]
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        return client.post(f"/books/{book_id}/generate", json={}).json()["package_id"]


def _pkg(client, book_id=None, package_id=None):
    """Pull the package dict from /books/{id}."""
    if book_id is None:
        book_id = client.get("/books").json()[0]["id"]
    packages = client.get(f"/books/{book_id}").json()["packages"]
    if package_id is not None:
        return next(p for p in packages if p["id"] == package_id)
    return packages[0]


# --- script ----------------------------------------------------------------


NEW_SCRIPT = (
    "## HOOK\nNew hook line.\n\n"
    "## WORLD TEASE\nNew world tease.\n\n"
    "## EMOTIONAL PULL\nNew emotional pull.\n\n"
    "## SOCIAL PROOF\n2M BookTok views.\n\n"
    "## CTA\nGrab the book now."
)


def test_patch_script_updates_and_flips_needs_rerender(client, package_id):
    res = client.patch(f"/packages/{package_id}", json={"script": NEW_SCRIPT})
    assert res.status_code == 200

    pkg = _pkg(client, package_id=package_id)
    assert pkg["script"] == NEW_SCRIPT
    assert pkg["needs_rerender"] is True


def test_patch_script_without_all_five_headers_is_400(client, package_id):
    missing_cta = (
        "## HOOK\nh\n\n"
        "## WORLD TEASE\nw\n\n"
        "## EMOTIONAL PULL\ne\n\n"
        "## SOCIAL PROOF\ns"
    )
    res = client.patch(f"/packages/{package_id}", json={"script": missing_cta})
    assert res.status_code == 400
    assert "cta" in res.json()["detail"].lower()


def test_patch_script_empty_is_400(client, package_id):
    res = client.patch(f"/packages/{package_id}", json={"script": "   "})
    assert res.status_code == 400


# --- chosen_hook_index -----------------------------------------------------


def test_patch_chosen_hook_index_in_range(client, package_id):
    res = client.patch(f"/packages/{package_id}", json={"chosen_hook_index": 2})
    assert res.status_code == 200
    assert _pkg(client, package_id=package_id)["chosen_hook_index"] == 2


def test_patch_chosen_hook_index_out_of_range_is_400(client, package_id):
    res = client.patch(f"/packages/{package_id}", json={"chosen_hook_index": 5})
    assert res.status_code == 400

    res = client.patch(f"/packages/{package_id}", json={"chosen_hook_index": -1})
    assert res.status_code == 400


def test_patch_chosen_hook_index_non_int_is_400(client, package_id):
    res = client.patch(f"/packages/{package_id}", json={"chosen_hook_index": "1"})
    assert res.status_code == 400


# --- visual_prompts --------------------------------------------------------


def test_patch_visual_prompts_updates_and_flips_needs_rerender(client, package_id):
    new_scenes = [
        {"section": "hook", "prompts": ["new hook image"], "focus": "f"},
        {"section": "world_tease", "prompts": ["world shot"], "focus": "f"},
        {"section": "emotional_pull", "prompts": ["grief motif"], "focus": "f"},
        {"section": "social_proof", "prompts": ["book on shelf"], "focus": "f"},
        {"section": "cta", "prompts": ["cozy reading nook"], "focus": "f"},
    ]
    res = client.patch(
        f"/packages/{package_id}", json={"visual_prompts": new_scenes}
    )
    assert res.status_code == 200

    pkg = _pkg(client, package_id=package_id)
    assert pkg["visual_prompts"] == new_scenes
    assert pkg["needs_rerender"] is True


def test_patch_visual_prompts_empty_scene_is_400(client, package_id):
    res = client.patch(
        f"/packages/{package_id}",
        json={"visual_prompts": [{"section": "hook", "prompts": [""]}]},
    )
    assert res.status_code == 400


def test_patch_visual_prompts_missing_section_or_label_is_400(client, package_id):
    res = client.patch(
        f"/packages/{package_id}",
        json={"visual_prompts": [{"prompts": ["x"], "focus": "f"}]},
    )
    assert res.status_code == 400


# --- titles + hashtags -----------------------------------------------------


def test_patch_titles_and_hashtags_no_rerender(client, package_id):
    """Meta-only edits save straight through and do NOT invalidate the mp4."""
    # Force a fresh state where needs_rerender could be either value — we
    # assert that the PATCH itself doesn't flip anything.
    before = _pkg(client, package_id=package_id)["needs_rerender"]

    new_titles = {**FAKE_META["titles"], "tiktok": "edited tt title"}
    new_hashtags = {**FAKE_META["hashtags"], "tiktok": ["#booktok", "#thriller"]}

    res = client.patch(
        f"/packages/{package_id}",
        json={"titles": new_titles, "hashtags": new_hashtags},
    )
    assert res.status_code == 200

    pkg = _pkg(client, package_id=package_id)
    assert pkg["titles"]["tiktok"] == "edited tt title"
    assert pkg["hashtags"]["tiktok"] == ["#booktok", "#thriller"]
    assert pkg["needs_rerender"] is before


def test_patch_hashtags_non_list_value_is_400(client, package_id):
    res = client.patch(
        f"/packages/{package_id}",
        json={"hashtags": {"tiktok": "not a list"}},
    )
    assert res.status_code == 400


# --- partial semantics + 404 ----------------------------------------------


def test_patch_partial_only_touches_named_keys(client, package_id):
    before = _pkg(client, package_id=package_id)

    res = client.patch(
        f"/packages/{package_id}",
        json={"titles": {**FAKE_META["titles"], "tiktok": "only title changed"}},
    )
    assert res.status_code == 200

    after = _pkg(client, package_id=package_id)
    assert after["script"] == before["script"]
    assert after["visual_prompts"] == before["visual_prompts"]
    assert after["chosen_hook_index"] == before["chosen_hook_index"]
    assert after["hashtags"] == before["hashtags"]
    assert after["titles"]["tiktok"] == "only title changed"


def test_patch_404_on_missing_package(client):
    assert client.patch("/packages/99999", json={"titles": {}}).status_code == 404


def test_patch_empty_payload_is_noop(client, package_id):
    """Sending {} should be valid — just a no-op commit."""
    res = client.patch(f"/packages/{package_id}", json={})
    assert res.status_code == 200
