"""ffmpeg-based video assembly — the desktop build's default renderer.

Why this exists
---------------
`services/renderer.py` assembles its final mp4 by shelling out to
`npx remotion render`, which requires Node + Chromium on the user's
machine. A ~150 MB runtime is acceptable for developers but not for a
double-click desktop app the plan targets. This module does the same
assembly step with **ffmpeg only** (already bundled with the desktop
build per A5) and keeps the rest of the pipeline — TTS, Whisper,
per-section image gen, duration math — identical.

Scope (by design, simpler than Remotion)
----------------------------------------
- Concatenates scene images at their computed per-scene durations.
- 1080×1920 (9:16), 30 fps, h264 + aac, MP4 container.
- Overlays burned-in word-level captions from `captions` (the same
  JSON shape Whisper produces). Font discovery is platform-aware;
  falls back to no-captions if no usable font is found.
- Narration audio is mixed at 1.0. Background music (when present) is
  ducked to 0.25 and mixed with the narration.

What's **not** supported (vs. Remotion path)
--------------------------------------------
- Tone-specific intro/outro cards with title/author. The Remotion
  composition renders those in React; reimplementing in ffmpeg
  filters is a lot of filter complexity for marginal polish. Callers
  pass `card_seconds=0` when invoking this renderer. A future pass
  can add `drawtext`-based cards if the user asks.
- Animated transitions between scenes. Hard cuts only.

These limits are acceptable for the desktop-default renderer. Power
users can still opt into the Remotion path via
`settings.renderer_backend = "remotion"`.
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Iterable


def find_font() -> Path | None:
    """Return an absolute path to a usable bold sans font, or None.

    Tried in order across platforms; caller should degrade gracefully
    (skip caption overlay) when None.
    """
    candidates = [
        # Linux (packaged ffmpeg containers, most distros)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Windows
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return Path(p)
    return None


def ffmpeg_binary() -> str:
    """Return the ffmpeg executable path.

    Honours `FFMPEG_PATH` (Tauri injects this pointing at the bundled
    binary in the app resources dir); falls back to `$PATH` lookup.
    """
    return os.environ.get("FFMPEG_PATH") or "ffmpeg"


def _escape_drawtext(text: str) -> str:
    # ffmpeg drawtext's `text=` is single-quoted; inside we need to
    # escape backslashes, single quotes, colons, and percent signs.
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
    )


def build_caption_filter(
    captions: Iterable[dict] | None,
    font_path: Path | None,
    video_width: int = 1080,
    video_height: int = 1920,
) -> str:
    """Return a comma-separated drawtext chain, or an empty string.

    Each caption dict must be `{word, start, end}` in seconds. Words
    with empty text or non-finite timings are skipped.
    """
    if not captions or font_path is None:
        return ""

    drawtexts: list[str] = []
    for c in captions:
        word = (c.get("word") or "").strip()
        start = c.get("start")
        end = c.get("end")
        if not word or start is None or end is None or end <= start:
            continue
        # Bottom third; boxed dark background for legibility on any image.
        drawtexts.append(
            "drawtext="
            f"fontfile='{font_path.as_posix()}':"
            f"text='{_escape_drawtext(word)}':"
            "fontsize=72:"
            "fontcolor=white:"
            "borderw=4:"
            "bordercolor=black@0.9:"
            "box=1:"
            "boxcolor=black@0.55:"
            "boxborderw=18:"
            "x=(w-text_w)/2:"
            f"y=h-{int(video_height * 0.22)}:"
            f"enable='between(t,{start:.3f},{end:.3f})'"
        )
    return ",".join(drawtexts)


def render_mp4(
    *,
    scene_images: list[Path],
    scene_durations: list[float],
    narration_mp3: Path,
    out_mp4: Path,
    captions: list[dict] | None = None,
    music_path: Path | None = None,
    video_width: int = 1080,
    video_height: int = 1920,
    fps: int = 30,
) -> None:
    """Build the mp4. Raises RuntimeError on ffmpeg failure.

    Shape of the filter graph (`N` = len(scene_images)):

        [0:v] scale+crop → [v0]
        [1:v] scale+crop → [v1]
        ...
        [v0][v1]...[v{N-1}] concat → [concatv]
        [concatv] drawtext (×captions) → [outv]    (optional)
        [N:a] (narration) [N+1:a] (music, ducked) amix → [outa]  (optional)
    """
    if not scene_images:
        raise ValueError("scene_images is empty")
    if len(scene_images) != len(scene_durations):
        raise ValueError(
            f"scene_images ({len(scene_images)}) / scene_durations "
            f"({len(scene_durations)}) length mismatch"
        )

    ffmpeg = ffmpeg_binary()
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    # One `-loop 1 -t <dur> -i <image>` per scene.
    cmd: list[str] = [ffmpeg, "-y"]
    for img, dur in zip(scene_images, scene_durations):
        cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(img)]
    narration_idx = len(scene_images)
    cmd += ["-i", str(narration_mp3)]
    music_idx = None
    if music_path is not None:
        music_idx = narration_idx + 1
        cmd += ["-i", str(music_path)]

    # Per-scene scale+crop to 9:16, force_original_aspect_ratio=increase
    # then crop to exact dims — same policy Remotion uses for Ken Burns
    # stills. `fps=<fps>` normalises the frame rate across all inputs.
    scale_crop = (
        f"scale={video_width}:{video_height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={video_width}:{video_height},"
        f"fps={fps},setsar=1,format=yuv420p"
    )
    filter_parts: list[str] = []
    concat_inputs: list[str] = []
    for i in range(len(scene_images)):
        filter_parts.append(f"[{i}:v]{scale_crop}[v{i}]")
        concat_inputs.append(f"[v{i}]")
    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={len(scene_images)}:v=1:a=0[concatv]"
    )

    caption_chain = build_caption_filter(
        captions, find_font(), video_width, video_height
    )
    if caption_chain:
        filter_parts.append(f"[concatv]{caption_chain}[outv]")
    else:
        filter_parts.append("[concatv]null[outv]")

    if music_idx is not None:
        # Duck music to 0.25, mix with narration at 1.0. `duration=first`
        # clips both to the length of the shortest — narration always
        # equals the scene total, so music is the one trimmed.
        filter_parts.append(
            f"[{narration_idx}:a]volume=1.0[na];"
            f"[{music_idx}:a]volume=0.25[mu];"
            "[na][mu]amix=inputs=2:duration=first:dropout_transition=0[outa]"
        )
        map_audio = ["-map", "[outa]"]
    else:
        map_audio = ["-map", f"{narration_idx}:a"]

    cmd += [
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        "[outv]",
        *map_audio,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out_mp4),
    ]

    use_shell = platform.system() == "Windows"
    proc = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        shell=use_shell,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-2000:]
        raise RuntimeError(
            f"ffmpeg render failed (exit {proc.returncode}):\n{tail}"
        )
