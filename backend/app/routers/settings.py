"""HTTP API for the Settings page.

Phase A6 of the desktop-packaging plan. The frontend Settings page
talks to this router to:

  GET    /settings                 — sanitised snapshot (never values)
  PUT    /settings/secrets/{name}  — write a single secret
  DELETE /settings/secrets/{name}  — clear a single secret
  PUT    /settings/providers       — flip provider routing toggles

Secrets are persisted to the OS keychain via
`app.services.secrets`. Provider routing toggles update the live
`Settings` singleton; in desktop mode they're persisted to a small
`settings.json` under `app_base_dir()` so they survive a restart.
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import APP_BASE_DIR, settings
from app.services import secrets as secrets_service


router = APIRouter()

# ---------------------------------------------------------------------------
# Provider enum allowlists. Keep in sync with backend/app/config.py.
# ---------------------------------------------------------------------------

ScriptProvider = Literal["claude", "openai", "qwen"]
MetaProvider = Literal["claude", "openai", "qwen"]
TtsProvider = Literal["openai", "kokoro", "dashscope", "elevenlabs"]
ImageProvider = Literal[
    "wanx", "dalle", "imagen", "replicate", "sdxl_local", "midjourney_manual"
]
RendererBackend = Literal["remotion", "ffmpeg"]


class ProviderUpdate(BaseModel):
    script_provider: ScriptProvider | None = None
    meta_provider: MetaProvider | None = None
    tts_provider: TtsProvider | None = None
    image_provider: ImageProvider | None = None
    renderer_backend: RendererBackend | None = None


class SecretBody(BaseModel):
    value: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# settings.json persistence (desktop only)
# ---------------------------------------------------------------------------


_PERSISTED_PROVIDER_FIELDS = (
    "script_provider",
    "meta_provider",
    "tts_provider",
    "image_provider",
    "renderer_backend",
)


def _settings_json_path():
    if APP_BASE_DIR is None:
        return None
    return APP_BASE_DIR / "settings.json"


def _load_persisted_providers() -> None:
    """Desktop boot: replay any provider toggles the user previously
    saved into settings.json onto the live Settings singleton.

    Called from the GET /settings handler so the snapshot reflects
    persisted values even when the bootstrap order didn't include
    this. No-op in dev (no settings.json exists)."""
    path = _settings_json_path()
    if path is None or not path.exists():
        return
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return
    for field in _PERSISTED_PROVIDER_FIELDS:
        value = data.get(field)
        if value:
            setattr(settings, field, value)


def _save_persisted_providers() -> None:
    """Desktop only: write the current provider toggles to
    settings.json so they survive a sidecar restart."""
    path = _settings_json_path()
    if path is None:
        return
    payload = {
        field: getattr(settings, field) for field in _PERSISTED_PROVIDER_FIELDS
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def _snapshot() -> dict:
    _load_persisted_providers()
    return {
        "secret_keys": secrets_service.all_status(),
        "providers": {
            "script": settings.script_provider,
            "meta": settings.meta_provider,
            "tts": settings.tts_provider,
            "image": settings.image_provider,
            "renderer": settings.renderer_backend,
        },
        "paths": {
            "renders_dir": settings.renders_dir,
            "music_dir": settings.music_dir,
            # Sanitise: don't return raw URLs that include credentials
            # for non-sqlite backends. SQLite paths are safe (file:///...).
            "database_url": (
                settings.database_url
                if settings.database_url.startswith("sqlite:")
                else "(redacted)"
            ),
        },
        "desktop_mode": secrets_service.is_desktop_mode(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def get_settings() -> dict:
    return _snapshot()


@router.put("/secrets/{name}")
def set_secret(name: str, body: SecretBody) -> dict:
    try:
        secrets_service.set(name, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return secrets_service.status(name)


@router.delete("/secrets/{name}")
def delete_secret(name: str) -> dict:
    try:
        secrets_service.clear(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return secrets_service.status(name)


@router.put("/providers")
def update_providers(body: ProviderUpdate) -> dict:
    """Pydantic enforces the enum allowlist on every field."""
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=400, detail="No provider fields to update"
        )
    for field, value in updates.items():
        setattr(settings, field, value)
    _save_persisted_providers()
    return _snapshot()
