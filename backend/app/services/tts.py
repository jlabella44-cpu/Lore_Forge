"""Pluggable text-to-speech layer.

Providers (select via TTS_PROVIDER env var):
- `openai`      — OpenAI TTS. $15/1M chars. 6 voices. Default.
                  Voice mapping by tone:
                    dark     → onyx
                    hype     → echo
                    cozy     → shimmer
- `kokoro`      — Kokoro TTS. Open source, runs on CPU, free. Good quality.
- `dashscope`   — Alibaba CosyVoice via Dashscope. Already-keyed fallback.
- `elevenlabs`  — ElevenLabs. Best quality, reserve for when voice is the brand.
"""
from __future__ import annotations

from typing import Literal

from app.config import settings

Provider = Literal["openai", "kokoro", "dashscope", "elevenlabs"]


# Tone → voice mapping, per provider.
VOICE_BY_TONE: dict[Provider, dict[str, str]] = {
    "openai": {"dark": "onyx", "hype": "echo", "cozy": "shimmer"},
    "kokoro": {"dark": "am_michael", "hype": "am_adam", "cozy": "af_bella"},
    "dashscope": {"dark": "longxiaochun", "hype": "longwan", "cozy": "longhua"},
    "elevenlabs": {"dark": "", "hype": "", "cozy": ""},  # fill from voice library
}


def synthesize(narration: str, tone: str, out_path: str) -> str:
    """Render narration audio to `out_path` (mp3). Returns the path.

    Phase 2 work — Remotion consumes the mp3 output.
    """
    provider: Provider = settings.tts_provider  # type: ignore[assignment]
    _ = VOICE_BY_TONE[provider].get(tone, next(iter(VOICE_BY_TONE[provider].values())))

    if provider == "openai":
        # from openai import OpenAI
        # client = OpenAI(api_key=settings.openai_api_key)
        # res = client.audio.speech.create(model="tts-1", voice=voice, input=narration)
        # res.stream_to_file(out_path)
        raise NotImplementedError("OpenAI TTS — Phase 2")
    if provider == "kokoro":
        # from kokoro import KPipeline   # pip install kokoro soundfile
        raise NotImplementedError("Kokoro TTS — Phase 2")
    if provider == "dashscope":
        # import dashscope; dashscope.audio.tts_v2...
        raise NotImplementedError("Dashscope CosyVoice — Phase 2")
    if provider == "elevenlabs":
        raise NotImplementedError("ElevenLabs TTS — Phase 2")
    raise ValueError(f"Unknown TTS provider: {provider}")
