"""HTTP tests for the /settings router.

The fake keyring backend pattern is shared with test_secrets.py;
duplicated here so this file is self-contained and can be moved
between modules without breaking the import graph.
"""
from __future__ import annotations

import json

import pytest

import keyring
from keyring.backend import KeyringBackend


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
def restore_settings():
    """Snapshot every secret + provider field on the live Settings
    before mutation, restore on teardown."""
    from app.config import settings
    from app.services import secrets as svc

    fields = list(svc.SECRET_KEYS) + [
        "script_provider",
        "meta_provider",
        "tts_provider",
        "image_provider",
        "renderer_backend",
    ]
    backup = {k: getattr(settings, k, None) for k in fields}
    yield
    for k, v in backup.items():
        setattr(settings, k, v if v is not None else "")


# ---------------------------------------------------------------------------
# GET /settings — sanitised snapshot
# ---------------------------------------------------------------------------


def test_get_returns_full_snapshot_shape(client, fake_keyring, restore_settings):
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {
        "secret_keys",
        "providers",
        "paths",
        "desktop_mode",
    }

    # secret_keys: list of {name, configured, last_four}; never values.
    for row in body["secret_keys"]:
        assert set(row) == {"name", "configured", "last_four"}
        assert isinstance(row["configured"], bool)

    # providers exposes all five toggle fields.
    assert set(body["providers"]) == {"script", "meta", "tts", "image", "renderer"}


def test_snapshot_marks_configured_secret(
    client, fake_keyring, restore_settings, monkeypatch
):
    """In dev mode, configured-ness is read off Settings, so writing
    via the env (or directly setting on Settings) flips the row to
    configured=True with the correct last_four."""
    from app.config import settings

    settings.openai_api_key = "sk-secret-2024"

    body = client.get("/settings").json()
    row = next(r for r in body["secret_keys"] if r["name"] == "openai_api_key")
    assert row == {
        "name": "openai_api_key",
        "configured": True,
        "last_four": "2024",
    }


def test_snapshot_never_returns_raw_values(
    client, fake_keyring, restore_settings
):
    from app.config import settings

    settings.anthropic_api_key = "sk-ant-NEVER-LEAK-ME"
    body = json.dumps(client.get("/settings").json())
    assert "NEVER-LEAK-ME" not in body


# ---------------------------------------------------------------------------
# PUT /settings/secrets/{name}
# ---------------------------------------------------------------------------


def test_put_secret_writes_value(client, fake_keyring, restore_settings):
    from app.config import settings

    res = client.put(
        "/settings/secrets/dashscope_api_key",
        json={"value": "ds-test-9999"},
    )
    assert res.status_code == 200, res.text
    assert res.json() == {
        "name": "dashscope_api_key",
        "configured": True,
        "last_four": "9999",
    }
    # Settings was mirrored.
    assert settings.dashscope_api_key == "ds-test-9999"


def test_put_secret_unknown_name_404(client, fake_keyring, restore_settings):
    res = client.put(
        "/settings/secrets/not_a_secret", json={"value": "x"}
    )
    assert res.status_code == 404
    assert "unknown secret" in res.json()["detail"]


def test_put_secret_rejects_empty_value(client, fake_keyring, restore_settings):
    # Pydantic min_length=1 → 422.
    res = client.put(
        "/settings/secrets/openai_api_key", json={"value": ""}
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /settings/secrets/{name}
# ---------------------------------------------------------------------------


def test_delete_secret_clears_value(client, fake_keyring, restore_settings):
    from app.config import settings

    settings.tiktok_client_key = "to-be-cleared"
    res = client.delete("/settings/secrets/tiktok_client_key")
    assert res.status_code == 200
    assert res.json()["configured"] is False
    assert settings.tiktok_client_key == ""


def test_delete_unknown_secret_404(client, fake_keyring, restore_settings):
    res = client.delete("/settings/secrets/not_a_secret")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# PUT /settings/providers
# ---------------------------------------------------------------------------


def test_put_providers_updates_subset(client, fake_keyring, restore_settings):
    from app.config import settings

    res = client.put(
        "/settings/providers",
        json={"script_provider": "openai", "renderer_backend": "ffmpeg"},
    )
    assert res.status_code == 200, res.text
    assert settings.script_provider == "openai"
    assert settings.renderer_backend == "ffmpeg"
    # Untouched.
    assert settings.image_provider == "wanx"

    # Snapshot reflects the change.
    snapshot = res.json()
    assert snapshot["providers"]["script"] == "openai"
    assert snapshot["providers"]["renderer"] == "ffmpeg"


def test_put_providers_rejects_unknown_value(
    client, fake_keyring, restore_settings
):
    res = client.put(
        "/settings/providers", json={"script_provider": "not_a_provider"}
    )
    assert res.status_code == 422  # pydantic enum check


def test_put_providers_empty_body_400(
    client, fake_keyring, restore_settings
):
    res = client.put("/settings/providers", json={})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Desktop persistence (settings.json round-trip)
# ---------------------------------------------------------------------------


def test_provider_changes_persist_to_settings_json(
    client, fake_keyring, restore_settings, tmp_path, monkeypatch
):
    """When APP_BASE_DIR is set, provider toggles are written to a
    `settings.json` so they survive a sidecar restart."""
    monkeypatch.setenv("LORE_FORGE_USER_DATA_DIR", str(tmp_path))
    # Re-bind APP_BASE_DIR on the module (the router reads it at
    # call time so the env-driven change takes effect immediately).
    from app.routers import settings as settings_router

    monkeypatch.setattr(settings_router, "APP_BASE_DIR", tmp_path)

    res = client.put(
        "/settings/providers", json={"image_provider": "dalle"}
    )
    assert res.status_code == 200

    persisted = json.loads((tmp_path / "settings.json").read_text())
    assert persisted["image_provider"] == "dalle"
