"""Approved package → 9:16 mp4 on disk.

Pipeline per render:
  1. Derive tone from the effective genre (override or auto).
  2. Stage a per-package working dir under `settings.renders_dir`.
  3. Synthesize narration mp3 (services/tts.py).
  4. Transcribe narration → word-level captions (services/whisper.py),
     persist to ContentPackage.captions. Skipped if captions already exist
     and the narration text hasn't changed since the last render.
  5. Generate one image per script section (services/images.py), writing
     scene_{NN}_{section}.png.
  6. Probe mp3 duration, compute per-scene duration from the package's
     section_word_counts, pad 2s of intro + 2s of outro.
  7. Pick a random tone-matched background music track (if any).
  8. Write Remotion props.json with {scenes, captions, audio, music, ...}
     and shell `npx remotion render`.
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
from pathlib import Path

from sqlalchemy.orm import object_session

from app.clock import utc_now
from app.config import settings
from app.observability import log_call
from app.services import images, tts, whisper


def narration_hash(text: str) -> str:
    """SHA-256 hex of the narration text, used for stale-render detection.

    Stored on ContentPackage.rendered_narration_hash at render time; compared
    against the current narration's hash to decide whether the on-disk mp4 is
    still in sync with the edit state.
    """
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

# Book genre → video tone.
GENRE_TONE: dict[str, str] = {
    "fantasy": "dark",
    "thriller": "dark",
    "scifi": "hype",
    "romance": "cozy",
    "historical_fiction": "cozy",
    "other": "dark",
}

# Canonical order — must match services.llm.SECTIONS. Importing from there
# would create a cycle at load time; these are intentionally duplicated,
# and the llm module's Stage 3 schema enforces the same ordering.
SECTIONS: list[str] = [
    "hook",
    "world_tease",
    "emotional_pull",
    "social_proof",
    "cta",
]


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
    if not package.section_word_counts:
        raise RuntimeError("Package has no section_word_counts")

    scenes_in = _normalize_scenes(package.visual_prompts)
    if len(scenes_in) != len(SECTIONS):
        raise RuntimeError(
            f"Expected {len(SECTIONS)} scene prompts, got {len(scenes_in)}"
        )

    genre = (book.genre_override or book.genre or "other")
    tone = tone_for(genre)

    work_dir = Path(settings.renders_dir).resolve() / str(package.id)
    work_dir.mkdir(parents=True, exist_ok=True)

    # The outer log_call wraps the whole pipeline so the summary line shows
    # total wall-clock; inner service-layer log_calls show per-stage timing.
    return _render_with_log(package, book, scenes_in, tone, work_dir)


def _render_with_log(package, book, scenes_in, tone, work_dir) -> dict:
    with log_call(
        "renderer.render_package",
        package_id=package.id,
        book_id=book.id,
        tone=tone,
        scene_count=len(scenes_in),
    ) as ctx:
        return _render_inner(package, book, scenes_in, tone, work_dir, ctx)


def _render_inner(package, book, scenes_in, tone, work_dir, ctx) -> dict:

    # 1. Narration
    narration_path = work_dir / "narration.mp3"
    tts.synthesize(package.narration, tone, narration_path)

    # 2. Captions — only re-transcribe if we don't have them yet
    if package.captions:
        captions = package.captions
    else:
        captions = whisper.transcribe_words(narration_path)
        package.captions = captions
        session = object_session(package)
        if session is not None:
            session.commit()

    # 3. Image gen — one per section, serial to keep Dashscope pressure low
    scene_paths: list[Path] = []
    for i, scene in enumerate(scenes_in, start=1):
        out = work_dir / f"scene_{i:02d}_{scene['section']}.png"
        images.generate(scene["prompt"], out, aspect="9:16")
        scene_paths.append(out)

    # 4. Duration math — split narration across sections by word count
    narration_seconds = probe_duration(narration_path)
    card_seconds = 2.0
    total_seconds = narration_seconds + card_seconds * 2

    per_scene_durations = _scene_durations_from_word_counts(
        package.section_word_counts, narration_seconds
    )

    ctx["narration_seconds"] = round(narration_seconds, 2)
    ctx["total_seconds"] = round(total_seconds, 2)

    # 5. Music (optional)
    music_path = pick_music_track(tone)

    # 6. Remotion props — new section-anchored shape
    props: dict = {
        "tone": tone,
        "title": book.title,
        "author": book.author,
        "cardSeconds": card_seconds,
        "scenes": [
            {
                "section": scene["section"],
                "image": str(path.resolve()),
                "durationSeconds": duration,
            }
            for scene, path, duration in zip(scenes_in, scene_paths, per_scene_durations)
        ],
        "audio": str(narration_path.resolve()),
        "captions": captions,
        "durationSeconds": total_seconds,
    }
    if music_path is not None:
        props["music"] = str(music_path.resolve())

    props_path = work_dir / "props.json"
    props_path.write_text(json.dumps(props, indent=2))

    # 7. Render
    out_mp4 = work_dir / "out.mp4"
    with log_call("renderer.remotion_cli", package_id=package.id):
        _run_remotion(props_path, out_mp4)

    size_bytes = out_mp4.stat().st_size
    ctx["size_mb"] = round(size_bytes / 1_048_576, 2)

    # 8. Snapshot the render on the package so the UI can show stats + detect
    # staleness without touching the filesystem. Hash is over the narration
    # that was actually spoken (which == package.narration at this point).
    package.rendered_at = utc_now()
    package.rendered_duration_seconds = total_seconds
    package.rendered_size_bytes = size_bytes
    package.rendered_narration_hash = narration_hash(package.narration)

    # 9. Advance the book's lifecycle state: scheduled → rendered. Only
    # transition from "scheduled" — leave "published" alone (re-render of a
    # live video shouldn't regress its status), and anything else (e.g.
    # "review" if the approval flow shifts) is out of scope for renderer.
    if book.status == "scheduled":
        book.status = "rendered"

    session = object_session(package)
    if session is not None:
        session.commit()

    return {
        "file_path": str(out_mp4),
        "duration_seconds": total_seconds,
        "size_bytes": size_bytes,
        "tone": tone,
        "work_dir": str(work_dir),
    }


# ---------------------------------------------------------------------------


def probe_duration(mp3_path: Path) -> float:
    from mutagen.mp3 import MP3

    return float(MP3(str(mp3_path)).info.length)


def pick_music_track(tone: str) -> Path | None:
    tone_dir = Path(settings.music_dir).resolve() / tone
    if not tone_dir.exists():
        return None
    tracks = [
        p
        for p in tone_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".m4a", ".wav", ".ogg"}
    ]
    if not tracks:
        return None
    return random.choice(tracks)


def _normalize_scenes(visual_prompts) -> list[dict]:
    """Accept both the new shape (list[{section, prompt, focus}]) and the
    legacy flat-string shape (list[str]) — the latter gets synthesized
    section labels in canonical order so old packages still render."""
    out: list[dict] = []
    for i, item in enumerate(visual_prompts):
        if isinstance(item, dict):
            out.append(
                {
                    "section": item.get("section") or SECTIONS[min(i, len(SECTIONS) - 1)],
                    "prompt": item.get("prompt", ""),
                    "focus": item.get("focus", ""),
                }
            )
        else:
            out.append(
                {
                    "section": SECTIONS[min(i, len(SECTIONS) - 1)],
                    "prompt": str(item),
                    "focus": "",
                }
            )
    return out


def _scene_durations_from_word_counts(
    section_word_counts: dict, narration_seconds: float
) -> list[float]:
    """Return a list of durations (seconds) for each section in canonical
    order, proportional to that section's narration word share.

    Floors each duration at 1.5s so a tiny CTA section still holds a
    readable slide — the overflow is absorbed evenly by longer sections.
    """
    counts = [max(0, int(section_word_counts.get(s, 0))) for s in SECTIONS]
    total_words = sum(counts)
    if total_words == 0:
        # Fall back to even split
        per = narration_seconds / len(SECTIONS)
        return [round(per, 3)] * len(SECTIONS)

    raw = [c / total_words * narration_seconds for c in counts]

    # Floor at 1.5s: top up from longer neighbors proportionally.
    floor = 1.5
    debt = 0.0
    result: list[float] = []
    for d in raw:
        if d < floor:
            debt += floor - d
            result.append(floor)
        else:
            result.append(d)
    if debt > 0:
        long_total = sum(r for r in result if r > floor)
        if long_total > 0:
            for i, r in enumerate(result):
                if r > floor:
                    result[i] = max(floor, r - debt * (r / long_total))
    return [round(x, 3) for x in result]


def _run_remotion(props_path: Path, out_mp4: Path) -> None:
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
    proc = subprocess.run(  # noqa: S603
        cmd,
        cwd=str(remotion_dir),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-2000:]
        raise RuntimeError(f"Remotion render failed (exit {proc.returncode}):\n{tail}")
