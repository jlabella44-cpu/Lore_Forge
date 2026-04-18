"""OS-keychain-backed secrets store.

Hermetic — every test installs a fake keyring backend via
`keyring.set_keyring(...)` so no real OS calls happen.
"""
from __future__ import annotations

import pytest

import keyring
from keyring.backend import KeyringBackend

from app.services import secrets as svc


# ---------------------------------------------------------------------------
# Fake in-memory keyring backend.
# ---------------------------------------------------------------------------


class _MemoryKeyring(KeyringBackend):
    priority = 1.0

    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) in self._store:
            del self._store[(service, username)]
        else:
            raise keyring.errors.PasswordDeleteError(
                f"no entry for {service}/{username}"
            )


@pytest.fixture
def fake_keyring():
    original = keyring.get_keyring()
    fake = _MemoryKeyring()
    keyring.set_keyring(fake)
    try:
        yield fake
    finally:
        keyring.set_keyring(original)


@pytest.fixture
def desktop_mode(monkeypatch):
    """Force desktop-mode by setting `LORE_FORGE_USER_DATA_DIR`. The
    Settings module-level cache (`APP_BASE_DIR`) was bound at import
    time, but `secrets.is_desktop_mode()` calls `app_base_dir()`
    fresh each time, so the env-var swap takes effect immediately."""
    monkeypatch.setenv("LORE_FORGE_USER_DATA_DIR", "/tmp/lore-forge-test-dt")
    yield


@pytest.fixture
def restore_settings():
    """Snapshot every secret-class field on the live Settings before a
    test mutates them, restore on teardown so other tests aren't
    affected."""
    from app.config import settings

    backup = {k: getattr(settings, k, None) for k in svc.SECRET_KEYS}
    yield
    for k, v in backup.items():
        setattr(settings, k, v if v is not None else "")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_unknown_key_raises():
    with pytest.raises(ValueError, match="unknown secret name"):
        svc.get("not_a_secret")


def test_set_rejects_non_string(restore_settings):
    with pytest.raises(TypeError, match="must be str"):
        svc.set("openai_api_key", 12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Dev mode (no keyring touched)
# ---------------------------------------------------------------------------


def test_dev_mode_get_reads_from_settings(restore_settings, monkeypatch):
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)
    from app.config import settings

    settings.openai_api_key = "sk-dev-1234"
    assert svc.get("openai_api_key") == "sk-dev-1234"


def test_dev_mode_set_only_touches_settings(
    restore_settings, fake_keyring, monkeypatch
):
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)
    from app.config import settings

    svc.set("nyt_api_key", "nyt-test-key")
    assert settings.nyt_api_key == "nyt-test-key"
    # Keyring stayed empty.
    assert fake_keyring._store == {}


def test_dev_mode_clear_only_touches_settings(
    restore_settings, fake_keyring, monkeypatch
):
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)
    from app.config import settings

    settings.dashscope_api_key = "to-clear"
    svc.clear("dashscope_api_key")
    assert settings.dashscope_api_key == ""
    assert fake_keyring._store == {}


def test_dev_mode_bootstrap_is_noop(
    restore_settings, fake_keyring, monkeypatch
):
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)
    from app.config import settings

    settings.openai_api_key = "from-env"
    fake_keyring.set_password(svc.SERVICE, "openai_api_key", "from-keyring")
    svc.bootstrap_into_settings()
    # Stays as-is — keyring isn't read in dev mode.
    assert settings.openai_api_key == "from-env"


# ---------------------------------------------------------------------------
# Desktop mode (keyring is the source of truth)
# ---------------------------------------------------------------------------


def test_desktop_set_writes_keyring_and_settings(
    restore_settings, fake_keyring, desktop_mode
):
    from app.config import settings

    svc.set("anthropic_api_key", "sk-ant-secret")
    assert fake_keyring.get_password(svc.SERVICE, "anthropic_api_key") == "sk-ant-secret"
    assert settings.anthropic_api_key == "sk-ant-secret"


def test_desktop_get_reads_keyring_first(
    restore_settings, fake_keyring, desktop_mode
):
    from app.config import settings

    settings.openai_api_key = "stale-from-env"
    fake_keyring.set_password(svc.SERVICE, "openai_api_key", "live-from-keyring")
    assert svc.get("openai_api_key") == "live-from-keyring"


def test_desktop_clear_removes_from_keyring_and_settings(
    restore_settings, fake_keyring, desktop_mode
):
    from app.config import settings

    fake_keyring.set_password(svc.SERVICE, "tiktok_client_key", "x")
    settings.tiktok_client_key = "x"

    svc.clear("tiktok_client_key")
    assert fake_keyring.get_password(svc.SERVICE, "tiktok_client_key") is None
    assert settings.tiktok_client_key == ""


def test_desktop_clear_unset_secret_is_idempotent(
    restore_settings, fake_keyring, desktop_mode
):
    # No entry exists — clear should not raise.
    svc.clear("nyt_api_key")
    assert svc.get("nyt_api_key") is None


def test_desktop_bootstrap_copies_keyring_to_settings(
    restore_settings, fake_keyring, desktop_mode
):
    from app.config import settings

    fake_keyring.set_password(svc.SERVICE, "openai_api_key", "boot-1")
    fake_keyring.set_password(svc.SERVICE, "dashscope_api_key", "boot-2")

    svc.bootstrap_into_settings()
    assert settings.openai_api_key == "boot-1"
    assert settings.dashscope_api_key == "boot-2"


# ---------------------------------------------------------------------------
# Status — never leaks the actual value
# ---------------------------------------------------------------------------


def test_status_returns_only_metadata(
    restore_settings, fake_keyring, desktop_mode
):
    svc.set("openai_api_key", "sk-abcd1234")
    s = svc.status("openai_api_key")
    assert s == {
        "name": "openai_api_key",
        "configured": True,
        "last_four": "1234",
    }
    # Sanity: the raw value never appears in the dict.
    for v in s.values():
        if isinstance(v, str):
            assert "abcd" not in v


def test_status_unset_is_not_configured(restore_settings, monkeypatch):
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)
    from app.config import settings

    settings.elevenlabs_api_key = ""
    s = svc.status("elevenlabs_api_key")
    assert s == {
        "name": "elevenlabs_api_key",
        "configured": False,
        "last_four": None,
    }


def test_all_status_covers_every_known_key():
    rows = svc.all_status()
    assert {r["name"] for r in rows} == set(svc.SECRET_KEYS)
