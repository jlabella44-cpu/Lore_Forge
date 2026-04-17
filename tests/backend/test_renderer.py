"""Renderer orchestrator + POST /packages/{id}/render."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_tone_for_maps_genres_correctly():
    from app.services.renderer import tone_for

    assert tone_for("fantasy") == "dark"
    assert tone_for("thriller") == "dark"
    assert tone_for("scifi") == "hype"
    assert tone_for("romance") == "cozy"
    assert tone_for("historical_fiction") == "cozy"
    assert tone_for("other") == "dark"
    assert tone_for(None) == "dark"
    assert tone_for("unknown_genre") == "dark"


def test_pick_music_track_returns_none_when_empty(tmp_path):
    from app.config import settings
    from app.services.renderer import pick_music_track

    orig = settings.music_dir
    settings.music_dir = str(tmp_path)
    try:
        # No tone dir exists → None
        assert pick_music_track("dark") is None

        # Empty tone dir → None
        (tmp_path / "dark").mkdir()
        assert pick_music_track("dark") is None
    finally:
        settings.music_dir = orig


def test_pick_music_track_chooses_from_tone_dir(tmp_path):
    from app.config import settings
    from app.services.renderer import pick_music_track

    (tmp_path / "hype").mkdir()
    t1 = tmp_path / "hype" / "one.mp3"
    t2 = tmp_path / "hype" / "two.m4a"
    t1.write_bytes(b"x")
    t2.write_bytes(b"x")
    # Non-audio file should be ignored
    (tmp_path / "hype" / "readme.txt").write_bytes(b"ignore me")

    orig = settings.music_dir
    settings.music_dir = str(tmp_path)
    try:
        picked = pick_music_track("hype")
        assert picked in (t1, t2)
    finally:
        settings.music_dir = orig


def test_probe_duration_reads_mp3(tmp_path):
    """Uses mutagen to read the mp3 length. Smoke-test with a mock."""
    from app.services import renderer

    fake_mp3 = MagicMock()
    fake_mp3.info.length = 87.5

    with patch("mutagen.mp3.MP3", return_value=fake_mp3):
        assert renderer.probe_duration(tmp_path / "x.mp3") == 87.5


# ---------- End-to-end render orchestration (everything mocked) ----------


@pytest.fixture
def approved_package(client, tmp_path, monkeypatch):
    """Seed a book + approved package via the API, with renders_dir pointed at tmp."""
    from app.config import settings

    monkeypatch.setattr(settings, "renders_dir", str(tmp_path / "renders"))
    monkeypatch.setattr(settings, "remotion_dir", str(tmp_path / "remotion"))
    monkeypatch.setattr(settings, "music_dir", str(tmp_path / "music"))

    nyt_hits = [
        {
            "title": "Night Circus",
            "author": "Erin Morgenstern",
            "isbn": "9780307744432",
            "description": "Two magicians duel in a mysterious circus.",
            "cover_url": None,
            "source_rank": 1,
        }
    ]
    hooks = {
        "alternatives": [
            {"angle": "curiosity", "text": "What if magic arrived overnight?"},
            {"angle": "fear", "text": "The circus vanishes at dawn."},
            {"angle": "promise", "text": "If you loved The Prestige, here's your next."},
        ],
        "chosen_index": 0,
        "rationale": "Curiosity fits fantasy.",
    }
    script_pkg = {
        "script": (
            "## HOOK\nWhat if magic arrived overnight?\n\n"
            "## WORLD TEASE\nA circus that only opens at dusk.\n\n"
            "## EMOTIONAL PULL\nYou will want to live inside it.\n\n"
            "## SOCIAL PROOF\nMillions of copies sold.\n\n"
            "## CTA\nLink in bio."
        ),
        "narration": "In a circus [PAUSE] that arrives without warning...",
        "section_word_counts": {
            "hook": 5, "world_tease": 7, "emotional_pull": 7,
            "social_proof": 4, "cta": 3,
        },
    }
    scene_pkg = {
        "scenes": [
            {"section": "hook", "prompt": "a moonlit circus tent", "focus": "stops scroll"},
            {"section": "world_tease", "prompt": "silhouettes in a mirror maze", "focus": "world"},
            {"section": "emotional_pull", "prompt": "a staircase of stars", "focus": "awe"},
            {"section": "social_proof", "prompt": "a stack of hardcovers", "focus": "sales"},
            {"section": "cta", "prompt": "a raven on a velvet rope", "focus": "cta"},
        ],
    }
    meta_pkg = {
        "titles": {"tiktok": "t", "yt_shorts": "y", "ig_reels": "i", "threads": "th"},
        "hashtags": {
            "tiktok": ["#booktok"],
            "yt_shorts": ["#shorts"],
            "ig_reels": ["#bookstagram"],
            "threads": ["#books"],
        },
    }

    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=nyt_hits),
        patch("app.services.llm.classify_genre", return_value=("fantasy", 0.9)),
    ):
        client.post("/discover/run")

    book_id = client.get("/books").json()[0]["id"]
    with (
        patch("app.services.llm.generate_hooks", return_value=hooks),
        patch("app.services.llm.generate_script", return_value=script_pkg),
        patch("app.services.llm.generate_scene_prompts", return_value=scene_pkg),
        patch("app.services.llm.generate_platform_meta", return_value=meta_pkg),
    ):
        gen = client.post(f"/books/{book_id}/generate", json={}).json()

    client.post(f"/packages/{gen['package_id']}/approve")
    return {"book_id": book_id, "package_id": gen["package_id"], "tmp": tmp_path}


def test_render_orchestrates_tts_images_and_remotion(client, approved_package):
    """End-to-end render with every external call stubbed out.

    Confirms the orchestrator: calls TTS with the right tone, calls image gen
    per prompt, probes mp3 duration, writes a props.json, shells out to
    Remotion, and returns the result shape the frontend expects.
    """
    pid = approved_package["package_id"]
    tmp = approved_package["tmp"]

    def fake_tts(narration, tone, out_path):
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"ID3fake_mp3_header")
        # Record the call so the test can assert on it
        fake_tts.captured = {"narration": narration, "tone": tone, "path": str(out_path)}
        return str(out_path)

    fake_tts.captured = None  # type: ignore[attr-defined]

    def fake_image(prompt, out_path, aspect="9:16"):
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return str(out_path)

    def fake_run(cmd, cwd, capture_output, text, **kwargs):
        # Simulate Remotion producing the out.mp4 on disk.
        out_mp4 = Path(cmd[cmd.index("LoreForge") + 1])
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"fake_mp4_bytes" * 1000)
        rv = MagicMock()
        rv.returncode = 0
        rv.stderr = ""
        return rv

    fake_captions = [
        {"word": "In", "start": 0.04, "end": 0.17},
        {"word": "a", "start": 0.18, "end": 0.22},
        {"word": "circus", "start": 0.23, "end": 0.74},
    ]

    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words", return_value=fake_captions),
        patch(
            "app.services.renderer.probe_duration", return_value=54.2
        ),
        patch("subprocess.run", side_effect=fake_run) as run_mock,
    ):
        res = client.post(f"/packages/{pid}/render")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["package_id"] == pid
    assert body["tone"] == "dark"  # fantasy → dark
    # Intro + outro pad 4s on top of 54.2s narration
    assert abs(body["duration_seconds"] - 58.2) < 1e-6
    assert body["file_path"].endswith("out.mp4")
    assert body["size_bytes"] > 0

    # TTS was called with the right tone
    assert fake_tts.captured["tone"] == "dark"
    assert fake_tts.captured["narration"].startswith("In a circus")

    # Remotion was invoked with the expected CLI args + a props.json on disk
    cmd, kwargs = run_mock.call_args.args, run_mock.call_args.kwargs
    assert cmd[0][:3] == ["npx", "remotion", "render"]
    props_arg = [a for a in cmd[0] if a.startswith("--props=")][0]
    props_path = Path(props_arg.removeprefix("--props="))
    assert props_path.exists()
    import json

    props = json.loads(props_path.read_text())
    assert props["tone"] == "dark"
    assert props["title"] == "Night Circus"

    # New scenes shape: 5 entries, each {section, image, durationSeconds}
    assert len(props["scenes"]) == 5
    for scene, expected_section in zip(props["scenes"], [
        "hook", "world_tease", "emotional_pull", "social_proof", "cta"
    ]):
        assert scene["section"] == expected_section
        assert scene["image"].endswith(".png")
        assert scene["durationSeconds"] > 0

    # Per-section durations should sum to the narration length (within 1e-2
    # for rounding) — not to total_duration; intro+outro hold the cards.
    scene_total = sum(s["durationSeconds"] for s in props["scenes"])
    assert abs(scene_total - 54.2) < 0.5  # tolerant: floor-at-1.5 rebalance

    # Captions flow through to props and get persisted on the package
    assert props["captions"] == fake_captions
    assert props["audio"].endswith("narration.mp3")
    assert props["durationSeconds"] == 58.2

    # Intermediate assets stayed in the per-package working dir
    work = tmp / "renders" / str(pid)
    assert (work / "narration.mp3").exists()
    # scene files now encode the section in the filename
    assert (work / "scene_01_hook.png").exists()
    assert (work / "scene_05_cta.png").exists()
    assert (work / "out.mp4").exists()

    # Captions persisted to the package
    detail = client.get(f"/books/{approved_package['book_id']}").json()
    approved = next(p for p in detail["packages"] if p["id"] == pid)
    assert approved["captions"] == fake_captions


def test_render_requires_approval(client, approved_package):
    """Generate a new revision (not approved) and try to render it."""
    pid = approved_package["package_id"]
    book_id = approved_package["book_id"]

    # Generate a fresh (un-approved) revision by mocking the full 4-stage chain.
    tiny_hooks = {
        "alternatives": [
            {"angle": "curiosity", "text": "x"},
            {"angle": "fear", "text": "y"},
            {"angle": "promise", "text": "z"},
        ],
        "chosen_index": 0,
        "rationale": "",
    }
    tiny_script = {
        "script": "## HOOK\nx\n\n## WORLD TEASE\ny\n\n## EMOTIONAL PULL\nz\n\n## SOCIAL PROOF\nw\n\n## CTA\nq",
        "narration": "x y z w q",
        "section_word_counts": {
            "hook": 1, "world_tease": 1, "emotional_pull": 1,
            "social_proof": 1, "cta": 1,
        },
    }
    tiny_scenes = {
        "scenes": [
            {"section": s, "prompt": "p", "focus": "f"}
            for s in ["hook", "world_tease", "emotional_pull", "social_proof", "cta"]
        ]
    }
    tiny_meta = {
        "titles": {"tiktok": "", "yt_shorts": "", "ig_reels": "", "threads": ""},
        "hashtags": {"tiktok": [], "yt_shorts": [], "ig_reels": [], "threads": []},
    }
    with (
        patch("app.services.llm.generate_hooks", return_value=tiny_hooks),
        patch("app.services.llm.generate_script", return_value=tiny_script),
        patch("app.services.llm.generate_scene_prompts", return_value=tiny_scenes),
        patch("app.services.llm.generate_platform_meta", return_value=tiny_meta),
    ):
        gen2 = client.post(f"/books/{book_id}/generate", json={"note": "v2"}).json()

    # Only v1 is approved; try rendering v2.
    res = client.post(f"/packages/{gen2['package_id']}/render")
    assert res.status_code == 400
    assert "approved" in res.json()["detail"].lower()


def test_render_404s_on_missing_package(client):
    assert client.post("/packages/99999/render").status_code == 404


def test_render_surfaces_remotion_failure(client, approved_package):
    pid = approved_package["package_id"]

    def fake_tts(*a, **kw):
        out = Path(a[2] if len(a) > 2 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def fake_image(*a, **kw):
        out = Path(a[1] if len(a) > 1 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def failing_remotion(cmd, cwd, capture_output, text, **kwargs):
        rv = MagicMock()
        rv.returncode = 1
        rv.stderr = "bundler exploded\nDetails here"
        return rv

    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words", return_value=[]),
        patch("app.services.renderer.probe_duration", return_value=30.0),
        patch("subprocess.run", side_effect=failing_remotion),
    ):
        res = client.post(f"/packages/{pid}/render")

    assert res.status_code == 500
    assert "Remotion render failed" in res.json()["detail"]
    assert "bundler exploded" in res.json()["detail"]


def test_render_skips_whisper_when_captions_already_persisted(client, approved_package):
    """Re-rendering a package with unchanged narration should not re-transcribe."""
    from app.db import SessionLocal
    from app.models import ContentPackage

    pid = approved_package["package_id"]
    pre_cached = [{"word": "cached", "start": 0.0, "end": 0.5}]

    # Seed captions directly so the renderer sees them on first pass.
    db = SessionLocal()
    try:
        pkg = db.get(ContentPackage, pid)
        pkg.captions = pre_cached
        db.commit()
    finally:
        db.close()

    def fake_tts(*a, **kw):
        out = Path(a[2] if len(a) > 2 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def fake_image(*a, **kw):
        out = Path(a[1] if len(a) > 1 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def fake_run(cmd, cwd, capture_output, text, **kwargs):
        out_mp4 = Path(cmd[cmd.index("LoreForge") + 1])
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"x")
        rv = MagicMock()
        rv.returncode = 0
        rv.stderr = ""
        return rv

    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words") as whisper_mock,
        patch("app.services.renderer.probe_duration", return_value=30.0),
        patch("subprocess.run", side_effect=fake_run) as run_mock,
    ):
        res = client.post(f"/packages/{pid}/render")

    assert res.status_code == 200
    whisper_mock.assert_not_called()

    # The cached captions flowed into Remotion props untouched
    import json
    props_arg = [a for a in run_mock.call_args.args[0] if a.startswith("--props=")][0]
    props = json.loads(Path(props_arg.removeprefix("--props=")).read_text())
    assert props["captions"] == pre_cached


# ---------- Render metadata persistence + stale-render detection ----------


def test_narration_hash_is_stable_and_sensitive_to_edits():
    from app.services.renderer import narration_hash

    assert narration_hash("hello") == narration_hash("hello")
    assert narration_hash("hello") != narration_hash("hello ")
    # 64-char hex (SHA-256)
    assert len(narration_hash("anything")) == 64


def test_render_persists_metadata_and_flips_needs_rerender(client, approved_package):
    """After a render: rendered_* columns populate and needs_rerender flips
    False. After a narration edit: it flips back True without touching disk."""
    from app.db import SessionLocal
    from app.models import ContentPackage
    from app.services.renderer import narration_hash

    pid = approved_package["package_id"]
    book_id = approved_package["book_id"]

    # Before render: needs_rerender = True because rendered_at is None.
    detail = client.get(f"/books/{book_id}").json()
    pkg = next(p for p in detail["packages"] if p["id"] == pid)
    assert pkg["needs_rerender"] is True
    assert pkg["rendered_at"] is None
    assert pkg["rendered_duration_seconds"] is None
    assert pkg["rendered_size_bytes"] is None

    def fake_tts(*a, **kw):
        out = Path(a[2] if len(a) > 2 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def fake_image(*a, **kw):
        out = Path(a[1] if len(a) > 1 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def fake_run(cmd, cwd, capture_output, text, **kwargs):
        out_mp4 = Path(cmd[cmd.index("LoreForge") + 1])
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"fake_mp4_bytes" * 500)
        rv = MagicMock()
        rv.returncode = 0
        rv.stderr = ""
        return rv

    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words", return_value=[]),
        patch("app.services.renderer.probe_duration", return_value=40.0),
        patch("subprocess.run", side_effect=fake_run),
    ):
        assert client.post(f"/packages/{pid}/render").status_code == 200

    # After render: all four fields populated; hash matches current narration.
    detail = client.get(f"/books/{book_id}").json()
    pkg = next(p for p in detail["packages"] if p["id"] == pid)
    assert pkg["needs_rerender"] is False
    assert pkg["rendered_at"] is not None
    assert pkg["rendered_duration_seconds"] == 44.0  # 40 narration + 2s + 2s
    assert pkg["rendered_size_bytes"] > 0

    # Edit the narration — needs_rerender flips without a file stat.
    db = SessionLocal()
    try:
        row = db.get(ContentPackage, pid)
        assert row.rendered_narration_hash == narration_hash(row.narration)
        row.narration = row.narration + " (edited)"
        db.commit()
    finally:
        db.close()

    detail = client.get(f"/books/{book_id}").json()
    pkg = next(p for p in detail["packages"] if p["id"] == pid)
    assert pkg["needs_rerender"] is True
    # But the persisted render stats from last time stay — the UI can still
    # show "last rendered N seconds ago" alongside the stale-warning.
    assert pkg["rendered_at"] is not None
    assert pkg["rendered_duration_seconds"] == 44.0


# ---------- Book lifecycle: scheduled → rendered on render success ----------


def _fake_render_triplet(tmp_path):
    """TTS/image/remotion stubs shared across the lifecycle tests."""

    def fake_tts(*a, **kw):
        out = Path(a[2] if len(a) > 2 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def fake_image(*a, **kw):
        out = Path(a[1] if len(a) > 1 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return str(out)

    def fake_run(cmd, cwd, capture_output, text, **kwargs):
        out_mp4 = Path(cmd[cmd.index("LoreForge") + 1])
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"x")
        rv = MagicMock()
        rv.returncode = 0
        rv.stderr = ""
        return rv

    return fake_tts, fake_image, fake_run


def test_render_transitions_book_scheduled_to_rendered(client, approved_package, tmp_path):
    """Approve leaves book.status = scheduled; a successful render flips it
    to rendered so the dashboard can filter 'approved + rendered, awaiting
    publish'."""
    pid = approved_package["package_id"]
    book_id = approved_package["book_id"]

    pre = client.get(f"/books/{book_id}").json()
    assert pre["status"] == "scheduled"

    fake_tts, fake_image, fake_run = _fake_render_triplet(tmp_path)
    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words", return_value=[]),
        patch("app.services.renderer.probe_duration", return_value=30.0),
        patch("subprocess.run", side_effect=fake_run),
    ):
        assert client.post(f"/packages/{pid}/render").status_code == 200

    post = client.get(f"/books/{book_id}").json()
    assert post["status"] == "rendered"


def test_rerender_does_not_clobber_published_status(client, approved_package, tmp_path):
    """Re-rendering a live video shouldn't regress book.status from
    published back to rendered."""
    from app.db import SessionLocal
    from app.models import Book

    pid = approved_package["package_id"]
    book_id = approved_package["book_id"]

    # Simulate the book having been published after an earlier render.
    db = SessionLocal()
    try:
        book = db.get(Book, book_id)
        book.status = "published"
        db.commit()
    finally:
        db.close()

    fake_tts, fake_image, fake_run = _fake_render_triplet(tmp_path)
    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words", return_value=[]),
        patch("app.services.renderer.probe_duration", return_value=30.0),
        patch("subprocess.run", side_effect=fake_run),
    ):
        assert client.post(f"/packages/{pid}/render").status_code == 200

    post = client.get(f"/books/{book_id}").json()
    assert post["status"] == "published"
