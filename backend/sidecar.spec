# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the desktop sidecar binary.

Run from the repo root:

    pyinstaller backend/sidecar.spec

Produces `dist/sidecar/sidecar[.exe]` — a single-file executable the
Tauri shell spawns at boot (see `src-tauri/tauri.conf.json::externalBin`).

One-file mode (bootloader unpacks to a temp dir on each launch) keeps
the Tauri integration simple — `externalBin` expects a single path per
target triple. The unpack cost is ~300ms on SSD, acceptable for an app
the user launches from the dock, not a server.

Bundles:
  * `db/` — alembic.ini + env.py + script.py.mako + versions/. The
    sidecar runs `alembic upgrade head` at boot via
    `app.migrations.run_migrations_to_head`.
  * `backend/assets/music/` — seeded per-tone music library the
    renderer reads from. Copied to the user-data dir on first launch
    (future A5 work — for now the renderer reads from here directly).
"""
from pathlib import Path

# `SPECPATH` is an implicit global PyInstaller sets to the spec's own
# directory — not the cwd. `.parent` hops up to the repo root so we can
# reference `db/` and `backend/...` from one place.
REPO_ROOT = Path(SPECPATH).parent  # noqa: F821  (SPECPATH is a PyInstaller builtin)

a = Analysis(
    [str(REPO_ROOT / "backend" / "sidecar.py")],
    pathex=[str(REPO_ROOT / "backend")],
    binaries=[],
    datas=[
        (str(REPO_ROOT / "db"), "db"),
        (str(REPO_ROOT / "backend" / "assets" / "music"), "assets/music"),
    ],
    hiddenimports=[
        # Alembic resolves migration modules dynamically; PyInstaller's
        # static analysis misses them. Listing the root package pulls the
        # versions/ files in via the `datas` entry above.
        "alembic.runtime.migration",
        "alembic.ddl.sqlite",
        "sqlalchemy.dialects.sqlite",
        # uvicorn loops / protocols picked at runtime based on the OS.
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not needed at runtime — saves ~40MB in the bundle.
        "tkinter",
        "pytest",
        "pyinstaller",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # stdout must reach the Tauri parent for the
                   # SIDECAR_READY handshake.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # set by CI per target triple
    codesign_identity=None,
    entitlements_file=None,
)
