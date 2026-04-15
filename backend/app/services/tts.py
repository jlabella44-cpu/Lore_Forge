"""Text-to-speech for narration rendering.

Providers (select via TTS_PROVIDER env var):
- `openai`      — OpenAI TTS. Default. $15/1M chars (~$0.014 / 90-sec short).
                  Voice mapping by tone: dark → onyx, hype → echo, cozy → shimmer.
- `kokoro`      — Kokoro TTS (open source, free, CPU). Phase 2+ stub.
- `dashscope`   — Alibaba CosyVoice via Dashscope. Phase 2+ stub.
- `elevenlabs`  — ElevenLabs. Phase 2+ stub.

The Claude-generated narration includes `[PAUSE]` markers for dramatic beats;
those get rewritten to "…" before synthesis so TTS reads them as a natural
pause rather than literal "pause".
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.config import settings

Provider = Literal["openai", "kokoro", "dashscope", "elevenlabs"]

# Tone → voice per provider. Only `openai` is wired in Phase 2; others keep
# the mapping so switching providers is a single env-var change later.
VOICE_BY_TONE: dict[Provider, dict[str, str]] = {
    "openai": {"dark": "onyx", "hype": "echo", "cozy": "shimmer"},
    "kokoro": {"dark": "am_michael", "hype": "am_adam", "cozy": "af_bella"},
    "dashscope": {"dark": "longxiaochun", "hype": "longwan", "cozy": "longhua"},
    "elevenlabs": {"dark": "", "hype": "", "cozy": ""},
}


def synthesize(narration: str, tone: str, out_path: str | Path) -> str:
    """Render narration mp3 at `out_path`. Returns the path as a string."""
    provider: Provider = settings.tts_provider  # type: ignore[assignment]
    voices = VOICE_BY_TONE[provider]
    voice = voices.get(tone) or next(iter(voices.values()))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = clean_narration_for_tts(narration)

    if provider == "openai":
        _openai_synthesize(text, voice, out_path)
    elif provider == "kokoro":
        raise NotImplementedError("Kokoro TTS — not yet wired (Phase 2+).")
    elif provider == "dashscope":
        raise NotImplementedError("Dashscope CosyVoice — not yet wired (Phase 2+).")
    elif provider == "elevenlabs":
        raise NotImplementedError("ElevenLabs TTS — not yet wired (Phase 2+).")
    else:
        raise ValueError(f"Unknown TTS provider: {provider!r}")

    return str(out_path)


def clean_narration_for_tts(text: str) -> str:
    """Rewrite [PAUSE] markers to an ellipsis so TTS voices the beat as a
    natural pause instead of reading "pause" out loud."""
    return text.replace("[PAUSE]", " … ").replace("  ", " ").strip()


# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=settings.openai_api_key)


def _openai_synthesize(text: str, voice: str, out_path: Path) -> None:
    """OpenAI TTS via the streaming-response pattern (handles arbitrary
    payload sizes without buffering the whole mp3 in memory)."""
    client = _openai_client()
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice=voice,
        input=text,
    ) as response:
        response.stream_to_file(str(out_path))
