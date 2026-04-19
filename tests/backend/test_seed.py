"""`app.seed.run` — demo data for the UI.

Only the lifecycle-related assertions live here: the rest of the seeded
package shape is exercised implicitly everywhere else in the suite.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_seed_scheduled_when_ffmpeg_missing(client, monkeypatch):
    """Without ffmpeg on PATH, the sample-video render is skipped and the
    book stays at 'scheduled' — same behavior as before the render-metadata
    work."""
    from app import seed

    monkeypatch.setattr(seed.shutil, "which", lambda _: None)
    stats = seed.run(wipe=True, with_video=True)

    assert stats["packages_created"] == 1
    assert stats["sample_video_rendered"] is False

    books = client.get("/items").json()
    # The fantasy book is the one with the package; find it + verify status.
    fantasy = next(b for b in books if b["genre"] == "fantasy")
    detail = client.get(f"/items/{fantasy['id']}").json()
    assert detail["status"] == "scheduled"
    pkg = detail["packages"][0]
    assert pkg["rendered_at"] is None
    assert pkg["needs_rerender"] is True


def test_seed_rendered_when_sample_video_succeeds(client, monkeypatch):
    """When ffmpeg produces the sample mp4, the seed bumps the book to
    `rendered` and mirrors the renderer's metadata snapshot on the package
    so the UI demo covers the new lifecycle node."""
    from app import seed

    monkeypatch.setattr(seed.shutil, "which", lambda _: "/usr/bin/ffmpeg")

    def fake_subprocess_run(cmd, check, capture_output, timeout):
        # cmd is the ffmpeg invocation; the last arg is the output path.
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake mp4 body" * 100)

        class _Result:
            returncode = 0
            stderr = b""
            stdout = b""

        return _Result()

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        stats = seed.run(wipe=True, with_video=True)

    assert stats["packages_created"] == 1
    assert stats["sample_video_rendered"] is True

    books = client.get("/items").json()
    fantasy = next(b for b in books if b["genre"] == "fantasy")
    detail = client.get(f"/items/{fantasy['id']}").json()
    assert detail["status"] == "rendered"

    pkg = detail["packages"][0]
    assert pkg["rendered_at"] is not None
    assert pkg["rendered_duration_seconds"] == 5.0
    assert pkg["rendered_size_bytes"] > 0
    # Narration hash matches current narration → not stale.
    assert pkg["needs_rerender"] is False
