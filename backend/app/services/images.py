"""Pluggable image generation layer.

Providers (select via IMAGE_PROVIDER env var):
- `wanx`             — Alibaba Wanx via Dashscope. Default — uses existing Qwen
                       key, has a free quota for new accounts.
                       Models: wanx2.1-t2i-turbo (cheap) | wanx2.1-t2i-plus (better).
- `dalle`            — OpenAI DALL-E 3. $0.04/image std. Already-keyed swap.
- `imagen`           — Google Imagen 3 via Gemini API. Free tier on AI Studio.
- `replicate`        — Replicate (FLUX.dev / SDXL). Pay per image.
- `sdxl_local`       — Self-hosted SDXL/FLUX on local GPU. Free, needs setup.
- `midjourney_manual`— No API. Emit prompts only; user pastes into Discord and
                       uploads returned PNGs.

All providers target **9:16** for shorts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.config import settings

Provider = Literal[
    "wanx",
    "dalle",
    "imagen",
    "replicate",
    "sdxl_local",
    "midjourney_manual",
]


def generate(prompt: str, out_dir: str | Path, *, aspect: str = "9:16") -> str:
    """Generate one image and return its local path.

    Phase 2 work. The pipeline will call this 4-5 times per video (one per
    visual prompt in the content package).
    """
    provider: Provider = settings.image_provider  # type: ignore[assignment]

    if provider == "wanx":
        # import dashscope; dashscope.ImageSynthesis.call(model="wanx2.1-t2i-turbo", ...)
        raise NotImplementedError("Wanx / Dashscope image gen — Phase 2")
    if provider == "dalle":
        # from openai import OpenAI; client.images.generate(model="dall-e-3", ...)
        raise NotImplementedError("DALL-E 3 — Phase 2")
    if provider == "imagen":
        # google-genai SDK
        raise NotImplementedError("Imagen 3 — Phase 2")
    if provider == "replicate":
        # import replicate; replicate.run("black-forest-labs/flux-dev", ...)
        raise NotImplementedError("Replicate FLUX — Phase 2")
    if provider == "sdxl_local":
        # diffusers pipeline
        raise NotImplementedError("Local SDXL — Phase 2")
    if provider == "midjourney_manual":
        # No API; the pipeline surfaces the prompt and pauses for a dropped file.
        raise NotImplementedError("Midjourney manual drop — Phase 2")
    raise ValueError(f"Unknown image provider: {provider}")
