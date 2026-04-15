"""Image generation for video stills.

Providers (select via IMAGE_PROVIDER env var):
- `wanx`             — Alibaba Wanx via Dashscope. Default — uses the same key
                       as Qwen chat. ~$0.02-0.04 per image on wanx2.1-t2i-turbo.
- `dalle`            — OpenAI DALL-E 3. Phase 2+ stub.
- `imagen`           — Google Imagen 3. Phase 2+ stub.
- `replicate`        — Replicate (FLUX / SDXL). Phase 2+ stub.
- `sdxl_local`       — Self-hosted SDXL on a local GPU. Phase 2+ stub.
- `midjourney_manual`— No API. Phase 2+ stub.

All providers target 9:16 for shorts.
"""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Literal

import httpx

from app.config import settings
from app.observability import log_call

Provider = Literal[
    "wanx",
    "dalle",
    "imagen",
    "replicate",
    "sdxl_local",
    "midjourney_manual",
]

# Default aspect → per-provider native size string. Remotion upscales to
# 1080x1920 at render time, so native 9:16 output doesn't need to be HD.
_WANX_SIZE_BY_ASPECT = {
    "9:16": "720*1280",
    "16:9": "1280*720",
    "1:1": "1024*1024",
}


def generate(prompt: str, out_path: str | Path, *, aspect: str = "9:16") -> str:
    """Render one image to `out_path`. Returns the path as a string."""
    provider: Provider = settings.image_provider  # type: ignore[assignment]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with log_call(
        "images.generate",
        provider=provider,
        aspect=aspect,
        out=out_path.name,
    ):
        if provider == "wanx":
            _wanx_generate(prompt, out_path, aspect)
        elif provider == "dalle":
            raise NotImplementedError("DALL-E 3 — not yet wired (Phase 2+).")
        elif provider == "imagen":
            raise NotImplementedError("Imagen 3 — not yet wired (Phase 2+).")
        elif provider == "replicate":
            raise NotImplementedError("Replicate FLUX — not yet wired (Phase 2+).")
        elif provider == "sdxl_local":
            raise NotImplementedError("Local SDXL — not yet wired (Phase 2+).")
        elif provider == "midjourney_manual":
            raise NotImplementedError(
                "Midjourney has no API — use IMAGE_PROVIDER=wanx or copy "
                "prompts into Discord manually."
            )
        else:
            raise ValueError(f"Unknown image provider: {provider!r}")

    return str(out_path)


# ---------------------------------------------------------------------------


def _wanx_generate(prompt: str, out_path: Path, aspect: str) -> None:
    """Dashscope → Wanx t2i → download the generated image to `out_path`.

    Dashscope returns a short-lived URL; we fetch it immediately and persist
    to disk so the renderer has a stable local path.
    """
    from dashscope import ImageSynthesis

    if not settings.dashscope_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not set")

    size = _WANX_SIZE_BY_ASPECT.get(aspect, _WANX_SIZE_BY_ASPECT["9:16"])
    rsp = ImageSynthesis.call(
        api_key=settings.dashscope_api_key,
        model="wanx2.1-t2i-turbo",
        prompt=prompt,
        n=1,
        size=size,
    )
    if rsp.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"Wanx error {rsp.status_code}: {getattr(rsp, 'code', '?')} "
            f"{getattr(rsp, 'message', '')}"
        )

    results = getattr(rsp.output, "results", None) or []
    if not results:
        raise RuntimeError("Wanx returned no image URL")
    url = results[0].url

    resp = httpx.get(url, timeout=60.0)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
