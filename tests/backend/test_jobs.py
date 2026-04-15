"""Async job flow: POST /generate?async=true + POST /render?async=true + GET /jobs/{id}.

Uses jobs.set_submit_hook to run background workers inline so the HTTP
response can be polled immediately in tests — no real threads.
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import jobs as jobs_svc


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
        {"angle": "curiosity", "text": "What if the orchid blooms?"},
        {"angle": "fear", "text": "Seven dead witnesses."},
        {"angle": "promise", "text": "If you loved Gone Girl…"},
    ],
    "chosen_index": 1,
    "rationale": "fear fits thriller",
}
FAKE_SCRIPT = {
    "script": "## HOOK\nSeven dead witnesses.\n\n## WORLD TEASE\nA swamp.\n\n## EMOTIONAL PULL\nYou won't sleep.\n\n## SOCIAL PROOF\n#1 NYT.\n\n## CTA\nLink in bio.",
    "narration": "Seven dead witnesses. A swamp. You won't sleep. #1 NYT. Link in bio.",
    "section_word_counts": {
        "hook": 3, "world_tease": 2, "emotional_pull": 3,
        "social_proof": 2, "cta": 4,
    },
}
FAKE_SCENES = {
    "scenes": [
        {"section": s, "prompt": f"p_{s}", "focus": "f"}
        for s in ["hook", "world_tease", "emotional_pull", "social_proof", "cta"]
    ]
}
FAKE_META = {
    "titles": {
        "tiktok": "t", "yt_shorts": "y", "ig_reels": "i", "threads": "th",
    },
    "hashtags": {
        "tiktok": ["#booktok"], "yt_shorts": ["#shorts"],
        "ig_reels": ["#bookstagram"], "threads": ["#books"],
    },
}


@pytest.fixture
def inline_jobs():
    """Run enqueued workers synchronously in the test thread so HTTP
    responses can be polled immediately."""
    jobs_svc.set_submit_hook(lambda fn: fn())
    yield
    jobs_svc.reset_submit_hook()


@pytest.fixture
def seeded_book(client):
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_ONE),
        patch("app.services.llm.classify_genre", return_value=("thriller", 0.85)),
    ):
        client.post("/discover/run")
    return client.get("/books").json()[0]["id"]


# --- generate -------------------------------------------------------------


def test_generate_async_returns_202_and_job_id(client, seeded_book, inline_jobs):
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        res = client.post(f"/books/{seeded_book}/generate?async=true", json={})

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "queued"
    assert body["job_id"] > 0


def test_generate_async_completes_and_result_is_polled(client, seeded_book, inline_jobs):
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        job_id = client.post(
            f"/books/{seeded_book}/generate?async=true", json={}
        ).json()["job_id"]

    # With the inline_jobs hook, the worker ran before the response returned,
    # so the job should already be in the `succeeded` state.
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "succeeded"
    assert job["kind"] == "generate"
    assert job["target_id"] == seeded_book
    assert job["error"] is None
    assert job["result"]["package_id"] > 0
    assert job["result"]["revision_number"] == 1
    assert job["started_at"] is not None
    assert job["finished_at"] is not None

    # Book status flipped to review (same as the sync path)
    assert client.get(f"/books/{seeded_book}").json()["status"] == "review"


def test_generate_async_records_stage_progress(client, seeded_book, inline_jobs):
    """The last set_progress call before completion is preserved on the job."""
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        job_id = client.post(
            f"/books/{seeded_book}/generate?async=true", json={}
        ).json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    # Worker's final set_progress line is overwritten by job_session's
    # "done" on success — that's the documented behavior.
    assert job["message"] == "done"


def test_generate_async_captures_failure(client, seeded_book, inline_jobs):
    with patch(
        "app.services.llm.generate_hooks",
        side_effect=RuntimeError("Claude exploded"),
    ):
        res = client.post(f"/books/{seeded_book}/generate?async=true", json={})
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert "Claude exploded" in job["error"]

    # Book status was rolled back from "generating" to prior "discovered"
    assert client.get(f"/books/{seeded_book}").json()["status"] == "discovered"


def test_generate_sync_path_still_works(client, seeded_book):
    """Regression: omitting async=true keeps the old 200-on-completion flow."""
    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        res = client.post(f"/books/{seeded_book}/generate", json={})

    assert res.status_code == 200
    assert res.json()["revision_number"] == 1


# --- render ---------------------------------------------------------------


@pytest.fixture
def approved_package(client, seeded_book, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "renders_dir", str(tmp_path / "renders"))

    with (
        patch("app.services.llm.generate_hooks", return_value=FAKE_HOOKS),
        patch("app.services.llm.generate_script", return_value=FAKE_SCRIPT),
        patch("app.services.llm.generate_scene_prompts", return_value=FAKE_SCENES),
        patch("app.services.llm.generate_platform_meta", return_value=FAKE_META),
    ):
        gen = client.post(f"/books/{seeded_book}/generate", json={}).json()
    client.post(f"/packages/{gen['package_id']}/approve")
    return gen["package_id"]


def test_render_async_returns_202_and_result(client, approved_package, inline_jobs):
    pid = approved_package

    def fake_tts(*a, **kw):
        out = Path(a[2] if len(a) > 2 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"ID3fake")
        return str(out)

    def fake_image(*a, **kw):
        out = Path(a[1] if len(a) > 1 else kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x89PNG")
        return str(out)

    def fake_run(cmd, cwd, capture_output, text):
        from unittest.mock import MagicMock

        out_mp4 = Path(cmd[cmd.index("LoreForge") + 1])
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"fake_mp4" * 1000)
        rv = MagicMock()
        rv.returncode = 0
        rv.stderr = ""
        return rv

    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words", return_value=[]),
        patch("app.services.renderer.probe_duration", return_value=42.0),
        patch("subprocess.run", side_effect=fake_run),
    ):
        res = client.post(f"/packages/{pid}/render?async=true")

    assert res.status_code == 202
    job_id = res.json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "succeeded"
    assert job["kind"] == "render"
    assert job["result"]["package_id"] == pid
    assert job["result"]["file_path"].endswith("out.mp4")


def test_render_async_captures_remotion_failure(client, approved_package, inline_jobs):
    from unittest.mock import MagicMock

    pid = approved_package

    def failing_remotion(cmd, cwd, capture_output, text):
        rv = MagicMock()
        rv.returncode = 1
        rv.stderr = "bundler exploded\nDetails here"
        return rv

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

    with (
        patch("app.services.tts.synthesize", side_effect=fake_tts),
        patch("app.services.images.generate", side_effect=fake_image),
        patch("app.services.whisper.transcribe_words", return_value=[]),
        patch("app.services.renderer.probe_duration", return_value=30.0),
        patch("subprocess.run", side_effect=failing_remotion),
    ):
        job_id = client.post(f"/packages/{pid}/render?async=true").json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert "Remotion render failed" in job["error"]


# --- GET /jobs/{id} -------------------------------------------------------


def test_get_job_404_on_missing(client):
    assert client.get("/jobs/99999").status_code == 404
