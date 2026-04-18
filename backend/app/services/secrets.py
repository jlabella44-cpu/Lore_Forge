"""OS-keychain-backed secrets store for the desktop build.

Phase A6 of the desktop-packaging plan. Production stores provider
API keys (Anthropic, OpenAI, Dashscope, ...) in the OS keychain
(macOS Keychain, Windows Credential Manager, Linux Secret Service)
instead of a plaintext .env file the user could accidentally commit.
Two operating modes:

  Desktop  (`app.paths.app_base_dir()` returns a real dir, i.e.
            `LORE_FORGE_DESKTOP=1` or LORE_FORGE_USER_DATA_DIR set):
            keyring is the source of truth. `bootstrap_into_settings()`
            reads every known secret out of keyring at boot and copies
            the live value onto the in-process `Settings` instance so
            the rest of the app sees them as if they were in env.

  Dev      (`app_base_dir()` returns None): keyring is bypassed.
            Settings keep their .env-loaded values. Set/clear ops
            update `Settings` in-memory only — the developer's keyring
            is never touched.

Secrets live under the `loreforge` service namespace, one entry per
key — `keyring.set_password("loreforge", "anthropic_api_key", "...")`.

`SECRET_KEYS` is the canonical allowlist of names the UI can manage.
Anything not in the list raises ValueError, so a typo in the router
can't open up arbitrary attribute writes on Settings.
"""
from __future__ import annotations

from typing import Iterable

import keyring

from app.config import settings
from app.paths import app_base_dir


SERVICE = "loreforge"


# Every secret-class field on Settings the UI is allowed to read,
# write, or clear. Keep alphabetical for predictable UI ordering.
SECRET_KEYS: tuple[str, ...] = (
    "amazon_associate_tag",
    "anthropic_api_key",
    "bookshop_affiliate_id",
    "dashscope_api_key",
    "elevenlabs_api_key",
    "firecrawl_api_key",
    "isbndb_api_key",
    "meta_app_id",
    "meta_app_secret",
    "nyt_api_key",
    "openai_api_key",
    "tiktok_client_key",
    "tiktok_client_secret",
    "youtube_client_id",
    "youtube_client_secret",
)


def is_desktop_mode() -> bool:
    """True when the app is running as the packaged sidecar (keyring
    is the source of truth) rather than dev (.env)."""
    return app_base_dir() is not None


def _validate(name: str) -> None:
    if name not in SECRET_KEYS:
        raise ValueError(
            f"unknown secret name {name!r} (allowed: {sorted(SECRET_KEYS)})"
        )


def get(name: str) -> str | None:
    """Return the current value of a secret, or None if unset.

    Reads from keyring in desktop mode; falls back to the live
    `Settings` attribute (which .env populated at boot) in dev.
    """
    _validate(name)
    if is_desktop_mode():
        return keyring.get_password(SERVICE, name)
    return getattr(settings, name, None) or None


def set(name: str, value: str) -> None:
    """Persist a secret. In desktop mode this writes to keyring AND
    mirrors the value onto the in-process `settings` object so the
    rest of the app picks it up immediately (no restart needed).
    """
    _validate(name)
    if not isinstance(value, str):
        raise TypeError(f"secret value must be str, got {type(value).__name__}")
    if is_desktop_mode():
        keyring.set_password(SERVICE, name, value)
    setattr(settings, name, value)


def clear(name: str) -> None:
    """Remove a secret. Idempotent — clearing an already-empty key
    succeeds silently."""
    _validate(name)
    if is_desktop_mode():
        try:
            keyring.delete_password(SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass
    setattr(settings, name, "")


def status(name: str) -> dict:
    """Return a sanitised view of a single secret — never the value."""
    _validate(name)
    raw = get(name) or ""
    return {
        "name": name,
        "configured": bool(raw),
        "last_four": raw[-4:] if len(raw) >= 4 else None,
    }


def all_status() -> list[dict]:
    return [status(k) for k in SECRET_KEYS]


def bootstrap_into_settings() -> None:
    """Desktop-only: copy every known secret from keyring into the
    `Settings` singleton at app boot.

    The lifespan in `backend/main.py` calls this once after
    `init_db()`. In dev mode this is a no-op so the developer's
    .env-loaded values stay authoritative.
    """
    if not is_desktop_mode():
        return
    for name in SECRET_KEYS:
        value = keyring.get_password(SERVICE, name)
        if value:
            setattr(settings, name, value)


# `set` shadows the Python built-in within this module; expose under a
# verbose alias for callers that prefer the explicit form.
set_secret = set
