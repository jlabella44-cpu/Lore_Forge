"""POST /books/{id}/generate (4-stage chain) + POST /packages/{id}/approve."""
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

# --- Fake responses for the four staged calls --------------------------------

FAKE_HOOKS = {
    "alternatives": [
        {"angle": "curiosity", "text": "What happens when the orchid blooms?"},
        {"angle": "fear", "text": "One flower. Seven dead witnesses."},
        {"angle": "promise", "text": "If you loved Gone Girl, this is next."},
    ],
    "chosen_index": 1,
    "rationale": "The fear angle works best for a thriller.",
}

FAKE_SCRIPT = {
    "script": (
        "## HOOK\nOne flower. Seven dead witnesses.\n\n"
        "## WORLD TEASE\nA swamp-town mystery that refuses to stay buried.\n\n"
        "## EMOTIONAL PULL\nYou will not put it down.\n\n"
        "## SOCIAL PROOF\n#1 NYT bestseller.\n\n"
        "## CTA\nLink in bio to grab it."
    ),
    "narration": (
        "One flower. [PAUSE] Seven dead witnesses. "
        "A swamp-town mystery that refuses to stay buried. "
        "You will not put it down. Number one NYT bestseller. "
        "Link in bio to grab it."
    ),
    "section_word_counts": {
        "hook": 6,
        "world_tease": 9,
        "emotional_pull": 6,
        "social_proof": 4,
        "cta": 5,
    },
}

FAKE_SCENES = {
    "scenes": [
        {
            "section": "hook",
            "prompt": "A single white orchid on dark water, moody fog",
            "focus": "stops the scroll",
        },
        {
            "section": "world_tease",
            "prompt": "A Southern swamp dock at dusk",
            "focus": "setting stakes",
        },
        {
            "section": "emotional_pull",
            "prompt": "A torn photograph drifting in murky water",
            "focus": "unresolved grief",
        },
        {
            "section": "social_proof",
            "prompt": "A stack of hardcovers with a #1 banner",
            "focus": "social proof: bestseller",
        },
        {
            "section": "cta",
            "prompt": "A leather-bound book under a warm reading lamp",
            "focus": "warm CTA",
        },
    ],
}

FAKE_META = {
    "titles": {
        "tiktok": "Seven dead witnesses. One orchid.",
        "yt_shorts": "The thriller that won't let you sleep",
        "ig_reels": "Cozy thriller autumn read",
        "threads": "Found my next obsession — Baldacci's swamp mystery",
    },
    "hashtags": {
        "tiktok": ["#booktok", "#thriller"],
        "yt_shorts": ["#shorts", "#booktok", "#thriller"],
        "ig_reels": ["#bookstagram", "#thriller"],
        "threads": ["#books", "#thrillers"],
    },
}


@pytest.fixture
def book_id(client):
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_ONE),
        patch("app.services.llm.classify_genre", return_value=("thriller", 0.85)),
    ):
        client.post("/discover/run")
    return client.get("/books").json()[0]["id"]


@pytest.fixture
def affiliate_env():
    from app.config import settings

    settings.amazon_associate_tag = "loreforge-20"
    settings.bookshop_affiliate_id = "loreforge"
    yield
    settings.amazon_associate_tag = ""
    settings.bookshop_affiliate_id = ""


# ---------- happy path -------------------------------------------------------


def test_generate_runs_the_four_stage_chain(client, book_id, affiliate_env):
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS) as h,
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT) as s,
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES) as sp,
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META) as m,
    ):
        res = client.post(f"/books/{book_id}/generate", json={})

    assert res.status_code == 200
    assert res.json()["revision_number"] == 1

    # Each stage was called exactly once.
    assert h.call_count == 1
    assert s.call_count == 1
    assert sp.call_count == 1
    assert m.call_count == 1

    # Stage 2 receives the chosen hook text verbatim (not the index).
    chosen_text = FAKE_HOOKS["alternatives"][FAKE_HOOKS["chosen_index"]]["text"]
    assert s.call_args.kwargs["chosen_hook"] == chosen_text


def test_generate_persists_all_new_fields(client, book_id, affiliate_env):
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        client.post(f"/books/{book_id}/generate", json={})

    detail = client.get(f"/books/{book_id}").json()
    pkg = detail["packages"][0]

    # Hook portfolio
    assert pkg["hook_alternatives"] == FAKE_HOOKS["alternatives"]
    assert pkg["chosen_hook_index"] == FAKE_HOOKS["chosen_index"]

    # Section-headered script + TTS-ready narration
    assert "## HOOK" in pkg["script"]
    assert "## WORLD TEASE" in pkg["script"]
    assert "[PAUSE]" in pkg["narration"]

    # Per-section word counts — all five keys present
    assert set(pkg["section_word_counts"]) == {
        "hook", "world_tease", "emotional_pull", "social_proof", "cta",
    }

    # Scene prompts — one per section, in order
    assert len(pkg["visual_prompts"]) == 5
    assert [v["section"] for v in pkg["visual_prompts"]] == [
        "hook", "world_tease", "emotional_pull", "social_proof", "cta",
    ]
    # Each scene carries prompt + focus
    for scene in pkg["visual_prompts"]:
        assert scene["prompt"]
        assert scene["focus"]

    # Platform meta
    assert pkg["titles"]["tiktok"].startswith("Seven dead")
    assert pkg["hashtags"]["yt_shorts"] == ["#shorts", "#booktok", "#thriller"]

    # Affiliate URLs built from real ISBN math
    assert pkg["affiliate_amazon"].startswith("https://www.amazon.com/dp/")
    assert "1538765381" in pkg["affiliate_amazon"]
    assert pkg["affiliate_bookshop"] == "https://bookshop.org/a/loreforge/9781538765388"

    # Captions stay null until the package is rendered
    assert pkg.get("captions") in (None, [])
    # is_approved starts false
    assert pkg["is_approved"] is False


def test_generate_threads_note_into_stage_2_only(client, book_id):
    """The regenerate note steers the script; stages 1 / 3 / 4 see no note."""
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS) as h,
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT) as s,
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES) as sp,
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META) as m,
    ):
        client.post(f"/books/{book_id}/generate", json={"note": "darker hook"})

    # Note threads into Stage 2
    assert s.call_args.kwargs["note"] == "darker hook"

    # Stages 1 / 3 / 4 don't take a `note` kwarg (they work from their own inputs)
    assert "note" not in h.call_args.kwargs
    assert "note" not in sp.call_args.kwargs
    assert "note" not in m.call_args.kwargs


def test_regenerate_increments_revision(client, book_id):
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        r1 = client.post(f"/books/{book_id}/generate", json={}).json()
        r2 = client.post(
            f"/books/{book_id}/generate", json={"note": "darker"}
        ).json()

    assert r1["revision_number"] == 1
    assert r2["revision_number"] == 2

    pkgs = client.get(f"/books/{book_id}").json()["packages"]
    assert [p["revision_number"] for p in pkgs] == [2, 1]
    # Newer rev carries the note; original doesn't
    by_rev = {p["revision_number"]: p for p in pkgs}
    assert by_rev[2]["regenerate_note"] == "darker"
    assert by_rev[1]["regenerate_note"] is None


# ---------- failure + guards -------------------------------------------------


def test_generate_rollback_on_any_stage_failure(client, book_id):
    """A failure in Stage 2 (or any stage) must not leave the book stuck
    in `generating` — router restores the prior status."""
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch(
            "app.services.llm.generate_script",
            side_effect=RuntimeError("Claude exploded mid-script"),
        ),
    ):
        res = client.post(f"/books/{book_id}/generate", json={})
    assert res.status_code == 502

    detail = client.get(f"/books/{book_id}").json()
    assert detail["status"] == "discovered"
    assert detail["packages"] == []


def test_generate_omits_affiliate_when_keys_missing(client, book_id):
    from app.config import settings

    assert settings.amazon_associate_tag == ""

    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        client.post(f"/books/{book_id}/generate", json={})

    pkg = client.get(f"/books/{book_id}").json()["packages"][0]
    assert pkg["affiliate_amazon"] is None
    assert pkg["affiliate_bookshop"] is None


# ---------- approve flow (unchanged semantics, still exercised) -------------


def test_approve_is_exclusive(client, book_id):
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        r1 = client.post(f"/books/{book_id}/generate", json={}).json()
        r2 = client.post(
            f"/books/{book_id}/generate", json={"note": "v2"}
        ).json()

    assert client.post(f"/packages/{r2['package_id']}/approve").status_code == 200
    detail = client.get(f"/books/{book_id}").json()
    assert detail["status"] == "scheduled"
    by_rev = {p["revision_number"]: p for p in detail["packages"]}
    assert by_rev[2]["is_approved"] is True
    assert by_rev[1]["is_approved"] is False

    client.post(f"/packages/{r1['package_id']}/approve")
    by_rev = {
        p["revision_number"]: p
        for p in client.get(f"/books/{book_id}").json()["packages"]
    }
    assert by_rev[1]["is_approved"] is True
    assert by_rev[2]["is_approved"] is False


def test_generate_and_approve_404s(client):
    assert client.post("/books/99999/generate").status_code == 404
    assert client.post("/packages/99999/approve").status_code == 404


# ---------- dossier cache --------------------------------------------------

_STUB_DOSSIER = {
    "setting": {"name": "", "era": "", "atmosphere": ""},
    "visual_motifs": [],
}


def test_second_generate_reuses_cached_dossier(client, book_id):
    """book_research.build_dossier is idempotent: the second /generate call
    on the same book must not re-run generate_book_dossier."""
    with (
        patch(
            "app.services.llm.generate_book_dossier",
            return_value=_STUB_DOSSIER,
        ) as dossier_llm,
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        client.post(f"/books/{book_id}/generate", json={})
        assert dossier_llm.call_count == 1

        # Second regen on the same book reads the persisted dossier.
        client.post(f"/books/{book_id}/generate", json={"note": "darker"})
        assert dossier_llm.call_count == 1
