"""Text-to-speech for narration rendering.

Providers (select via TTS_PROVIDER env var):
- `openai`      — OpenAI TTS. Default. $15/1M chars (~$0.014 / 90-sec short).
                  Model configurable via TTS_MODEL (default tts-1-hd).
                  Voice + speed mapped by tone for emotional range.
- `kokoro`      — Kokoro TTS (open source, free, CPU). Phase 2+ stub.
- `dashscope`   — Alibaba CosyVoice via Dashscope. Phase 2+ stub.
- `elevenlabs`  — ElevenLabs. Phase 2+ stub.

The Claude-generated narration includes `[PAUSE]` markers for dramatic beats
and `[BREAK]` markers for section transitions. Both are converted to natural
pauses before synthesis.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.config import settings
from app.observability import log_call
from app.services import cost

Provider = Literal["openai", "kokoro", "dashscope", "elevenlabs"]

# Tone → voice per provider.
VOICE_BY_TONE: dict[Provider, dict[str, str]] = {
    "openai": {"dark": "onyx", "hype": "nova", "cozy": "shimmer"},
    "kokoro": {"dark": "am_michael", "hype": "am_adam", "cozy": "af_bella"},
    "dashscope": {"dark": "longxiaochun", "hype": "longwan", "cozy": "longhua"},
    "elevenlabs": {"dark": "", "hype": "", "cozy": ""},
}

# Tone → speech speed. Slower for dramatic, faster for energetic.
SPEED_BY_TONE: dict[str, float] = {
    "dark": 0.9,
    "hype": 1.1,
    "cozy": 0.95,
}


def synthesize(narration: str, tone: str, out_path: str | Path) -> str:
    """Render narration mp3 at `out_path`. Returns the path as a string."""
    provider: Provider = settings.tts_provider  # type: ignore[assignment]
    voices = VOICE_BY_TONE[provider]
    voice = voices.get(tone) or next(iter(voices.values()))
    speed = SPEED_BY_TONE.get(tone, 1.0)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = clean_narration_for_tts(narration)
    model = getattr(settings, "tts_model", "tts-1-hd") or "tts-1-hd"

    with log_call(
        "tts.synthesize",
        provider=provider,
        tone=tone,
        voice=voice,
        speed=speed,
        model=model,
        chars=len(text),
    ):
        if provider == "openai":
            _openai_synthesize(text, voice, speed, model, out_path)
            try:
                cost.record_tts(provider="openai", model=model, chars=len(text))
            except Exception:
                pass
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
    """Rewrite markers to natural pauses for TTS:
    - [PAUSE] → single ellipsis (short beat)
    - [BREAK] → triple ellipsis (longer section transition)
    """
    text = text.replace("[BREAK]", " … … … ")
    text = text.replace("[PAUSE]", " … ")
    # Collapse whitespace
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=settings.openai_api_key)


def _openai_synthesize(
    text: str, voice: str, speed: float, model: str, out_path: Path
) -> None:
    """OpenAI TTS via the streaming-response pattern (handles arbitrary
    payload sizes without buffering the whole mp3 in memory)."""
    client = _openai_client()
    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        speed=speed,
        input=text,
    ) as response:
        response.stream_to_file(str(out_path))
