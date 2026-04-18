"""ffmpeg-based simple_renderer — the desktop-default video assembler.

These tests drive the real ffmpeg binary (the desktop build bundles
one). If ffmpeg isn't on PATH the whole module is skipped so CI boxes
without it stay green.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from app.services.simple_renderer import (
    build_caption_filter,
    find_font,
    render_mp4,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


# ---------------------------------------------------------------------------
# Helpers to fabricate tiny inputs without pulling in Pillow / numpy.
# ---------------------------------------------------------------------------


def _write_solid_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    """Emit a valid solid-colour PNG. 8-bit RGB, no interlace.

    Hand-rolled so tests don't depend on Pillow. ffmpeg accepts this
    just fine as a scene image.
    """
    r, g, b = rgb
    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # filter byte per scanline
        raw.extend(bytes([r, g, b]) * width)
    compressed = zlib.compress(bytes(raw))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        signature
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def _write_silent_mp3(path: Path, seconds: float) -> None:
    """Generate a real mp3 via ffmpeg. Keeps the dep surface to ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=24000:cl=mono:d={seconds}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "9",
            str(path),
        ],
        capture_output=True,
        check=True,
    )


# ---------------------------------------------------------------------------
# Caption filter builder (pure function; no ffmpeg needed).
# ---------------------------------------------------------------------------


def test_build_caption_filter_empty_when_no_font(tmp_path):
    # Even with captions, no font → empty filter (caller falls back).
    captions = [{"word": "hello", "start": 0.0, "end": 0.5}]
    assert build_caption_filter(captions, font_path=None) == ""


def test_build_caption_filter_empty_when_no_captions(tmp_path):
    font = tmp_path / "fake.ttf"
    font.write_bytes(b"")
    assert build_caption_filter(None, font) == ""
    assert build_caption_filter([], font) == ""


def test_build_caption_filter_emits_one_drawtext_per_word(tmp_path):
    font = tmp_path / "fake.ttf"
    font.write_bytes(b"")
    captions = [
        {"word": "hello", "start": 0.0, "end": 0.3},
        {"word": "world", "start": 0.3, "end": 0.6},
    ]
    out = build_caption_filter(captions, font)
    assert out.count("drawtext=") == 2
    assert "hello" in out
    assert "world" in out
    # Windows should be enabled only during its own span.
    assert "between(t,0.000,0.300)" in out
    assert "between(t,0.300,0.600)" in out


def test_build_caption_filter_skips_malformed_words(tmp_path):
    font = tmp_path / "fake.ttf"
    font.write_bytes(b"")
    captions = [
        {"word": "", "start": 0, "end": 0.1},          # empty
        {"word": "ok", "start": 0.1, "end": 0.1},      # zero-length
        {"word": "ok", "start": 0.2, "end": 0.1},      # backwards
        {"word": None, "start": 0, "end": 0.1},        # None text
        {"word": "good", "start": 0.4, "end": 0.6},    # valid
    ]
    out = build_caption_filter(captions, font)
    assert out.count("drawtext=") == 1
    assert "good" in out


def test_build_caption_filter_escapes_special_chars(tmp_path):
    font = tmp_path / "fake.ttf"
    font.write_bytes(b"")
    captions = [{"word": "it's: 50% off", "start": 0, "end": 0.5}]
    out = build_caption_filter(captions, font)
    # Single quote, colon, and percent must all be escaped for drawtext.
    assert r"\'" in out
    assert r"\:" in out
    assert r"\%" in out


# ---------------------------------------------------------------------------
# End-to-end: real ffmpeg, tiny inputs.
# ---------------------------------------------------------------------------


def test_render_mp4_writes_valid_file(tmp_path):
    scene1 = tmp_path / "s1.png"
    scene2 = tmp_path / "s2.png"
    _write_solid_png(scene1, 160, 284, (200, 40, 40))   # 9:16-ish
    _write_solid_png(scene2, 160, 284, (40, 200, 40))

    narration = tmp_path / "narration.mp3"
    _write_silent_mp3(narration, seconds=1.2)

    out = tmp_path / "out.mp4"
    render_mp4(
        scene_images=[scene1, scene2],
        scene_durations=[0.6, 0.6],
        narration_mp3=narration,
        out_mp4=out,
        captions=None,
        music_path=None,
        # Small dims keep the test fast.
        video_width=180,
        video_height=320,
        fps=15,
    )

    assert out.exists()
    # First bytes of an MP4 start with an ftyp box.
    header = out.read_bytes()[:12]
    assert b"ftyp" in header, f"not an mp4: {header!r}"
    # >0 bytes, smaller than a real render, large enough to contain frames.
    size = out.stat().st_size
    assert 500 < size < 5_000_000


def test_render_mp4_with_captions_burns_them_in(tmp_path):
    if find_font() is None:
        pytest.skip("no usable font found on this host")

    scene = tmp_path / "s.png"
    _write_solid_png(scene, 180, 320, (20, 20, 20))

    narration = tmp_path / "narration.mp3"
    _write_silent_mp3(narration, seconds=1.0)

    captions = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]

    out = tmp_path / "out.mp4"
    render_mp4(
        scene_images=[scene],
        scene_durations=[1.0],
        narration_mp3=narration,
        out_mp4=out,
        captions=captions,
        video_width=180,
        video_height=320,
        fps=15,
    )
    assert out.exists()
    assert out.stat().st_size > 500


def test_render_mp4_raises_on_mismatched_inputs(tmp_path):
    narration = tmp_path / "narration.mp3"
    narration.write_bytes(b"")

    with pytest.raises(ValueError, match="scene_images is empty"):
        render_mp4(
            scene_images=[],
            scene_durations=[],
            narration_mp3=narration,
            out_mp4=tmp_path / "out.mp4",
        )

    scene = tmp_path / "s.png"
    _write_solid_png(scene, 20, 20, (0, 0, 0))
    with pytest.raises(ValueError, match="length mismatch"):
        render_mp4(
            scene_images=[scene],
            scene_durations=[1.0, 1.0],  # wrong length
            narration_mp3=narration,
            out_mp4=tmp_path / "out.mp4",
        )
