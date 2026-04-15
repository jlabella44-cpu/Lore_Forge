"""Approved package → 9:16 mp4 on disk.

Pipeline per render:
  1. Derive tone from the effective genre (override or auto).
  2. Stage a per-package working dir under `settings.renders_dir`.
  3. Synthesize narration mp3 (services/tts.py).
  4. Generate one image per visual_prompt (services/images.py).
  5. Probe the narration mp3 length → `durationSeconds`.
  6. Pick a random tone-matched background music track (if any).
  7. Write a Remotion props.json and shell `npx remotion render`.
  8. Return the output mp4 path + metadata.

Every intermediate asset lands in the same working dir so a failed render
leaves evidence behind; a successful re-render overwrites cleanly.
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

from app.config import settings
from app.services import images, tts

# Book genre → video tone. Fantasy + thriller share the "dark" template;
# scifi gets "hype"; romance + historical_fiction share "cozy"; anything
# uncategorized defaults to "dark" (looks fine, reads serious).
GENRE_TONE: dict[str, str] = {
    "fantasy": "dark",
    "thriller": "dark",
    "scifi": "hype",
    "romance": "cozy",
    "historical_fiction": "cozy",
    "other": "dark",
}


def tone_for(genre: str | None) -> str:
    return GENRE_TONE.get(genre or "other", "dark")


def render_package(package, book) -> dict:
    """End-to-end render. Returns:
        {file_path, duration_seconds, size_bytes, tone, work_dir}
    """
    if not package.is_approved:
        raise RuntimeError("Package must be approved before rendering")
    if not package.narration:
        raise RuntimeError("Package has no narration text")
    if not package.visual_prompts:
        raise RuntimeError("Package has no visual prompts")

    genre = (book.genre_override or book.genre or "other")
    tone = tone_for(genre)

    work_dir = Path(settings.renders_dir).resolve() / str(package.id)
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Narration
    narration_path = work_dir / "narration.mp3"
    tts.synthesize(package.narration, tone, narration_path)

    # 2. Images — serial; 4-5 prompts × ~8s each is fine, parallelism adds
    # rate-limit risk on Dashscope without much wall-clock win.
    image_paths: list[Path] = []
    for i, prompt in enumerate(package.visual_prompts, start=1):
        out = work_dir / f"scene_{i:02d}.png"
        images.generate(prompt, out, aspect="9:16")
        image_paths.append(out)

    # 3. Duration — TTS gives us the narration length; pad intro + outro
    # cards (2s each by default) on top.
    narration_seconds = probe_duration(narration_path)
    card_seconds = 2.0
    total_seconds = narration_seconds + card_seconds * 2

    # 4. Music (optional)
    music_path = pick_music_track(tone)

    # 5. Remotion props
    props: dict = {
        "tone": tone,
        "title": book.title,
        "author": book.author,
        "cardSeconds": card_seconds,
        "images": [str(p.resolve()) for p in image_paths],
        "audio": str(narration_path.resolve()),
        "durationSeconds": total_seconds,
    }
    if music_path is not None:
        props["music"] = str(music_path.resolve())

    props_path = work_dir / "props.json"
    props_path.write_text(json.dumps(props, indent=2))

    # 6. Render
    out_mp4 = work_dir / "out.mp4"
    _run_remotion(props_path, out_mp4)

    return {
        "file_path": str(out_mp4),
        "duration_seconds": total_seconds,
        "size_bytes": out_mp4.stat().st_size,
        "tone": tone,
        "work_dir": str(work_dir),
    }


# ---------------------------------------------------------------------------


def probe_duration(mp3_path: Path) -> float:
    """Return mp3 length in seconds via mutagen. ~1ms for a 90-sec file."""
    from mutagen.mp3 import MP3

    return float(MP3(str(mp3_path)).info.length)


def pick_music_track(tone: str) -> Path | None:
    """Return a random track from `music_dir/{tone}/`, or None if empty."""
    tone_dir = Path(settings.music_dir).resolve() / tone
    if not tone_dir.exists():
        return None
    tracks = [
        p for p in tone_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".m4a", ".wav", ".ogg"}
    ]
    if not tracks:
        return None
    return random.choice(tracks)


def _run_remotion(props_path: Path, out_mp4: Path) -> None:
    """Shell out to `npx remotion render` from the /remotion dir."""
    remotion_dir = Path(settings.remotion_dir).resolve()
    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.ts",
        "LoreForge",
        str(out_mp4.resolve()),
        f"--props={props_path.resolve()}",
    ]
    proc = subprocess.run(  # noqa: S603 — command list, not shell=True
        cmd,
        cwd=str(remotion_dir),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # Keep the tail of stderr — Remotion is chatty on the happy path too.
        tail = (proc.stderr or "")[-2000:]
        raise RuntimeError(f"Remotion render failed (exit {proc.returncode}):\n{tail}")
