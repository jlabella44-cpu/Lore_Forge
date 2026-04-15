"""Word-level transcription via OpenAI Whisper.

Called at render time (not generate time) so captions sync to the exact
narration mp3 the renderer is about to hand Remotion — no drift.

Cost: $0.006 / audio-minute. A 90-sec short is ~$0.009 / render. Whisper's
`verbose_json` response includes per-word timestamps when we ask for
`timestamp_granularities: ["word"]`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import settings


@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=settings.openai_api_key)


def transcribe_words(mp3_path: str | Path) -> list[dict]:
    """Return a word-level transcript: [{word, start, end}, ...] in seconds.

    Returns an empty list if Whisper returned no words (e.g. a silent clip).
    """
    client = _openai_client()
    with open(mp3_path, "rb") as fh:
        resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=fh,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = getattr(resp, "words", None) or []
    return [
        {"word": w.word, "start": float(w.start), "end": float(w.end)}
        for w in words
    ]
