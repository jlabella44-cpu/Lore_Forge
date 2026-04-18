"""Desktop-sidecar entry point.

The Tauri shell spawns this process as the application backend. Protocol:

1. On boot we set `LORE_FORGE_DESKTOP=1` so `app.paths.app_base_dir()`
   anchors every runtime path at the OS user-data dir. An explicit
   `LORE_FORGE_USER_DATA_DIR` (set by Tauri) takes precedence.
2. We pick a loopback port — either `LORE_FORGE_SIDECAR_PORT` from the
   env (Tauri can pre-assign) or a fresh one from the kernel.
3. We print a single line `SIDECAR_READY http://127.0.0.1:<port>` to
   stdout so the Rust side can parse it before any uvicorn log noise.
   The parent waits for `GET /health` to return 200 before showing the
   window; that handshake is short (< 1s on a cold disk).
4. uvicorn takes over the process. Lifespan in `backend/main.py` runs
   alembic to head before accepting requests.

This file is the PyInstaller entry point (`sidecar.spec`). In dev, run
directly: `python backend/sidecar.py`.
"""
from __future__ import annotations

import os
import socket
import sys

# Must be set BEFORE `app.*` imports so `config.APP_BASE_DIR` is non-None
# at module-import time.
os.environ.setdefault("LORE_FORGE_DESKTOP", "1")


def _pick_port() -> int:
    explicit = os.environ.get("LORE_FORGE_SIDECAR_PORT")
    if explicit:
        return int(explicit)
    # SO_REUSEADDR + immediate close leaves a tiny race window where the
    # port could be taken by another process before uvicorn binds; in
    # practice this has never surfaced, and uvicorn will fail loudly if
    # it does. Good enough for a single-user desktop app.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    port = _pick_port()
    # Print ONCE, flush, before uvicorn starts logging. The Rust side
    # greps for this exact prefix.
    sys.stdout.write(f"SIDECAR_READY http://127.0.0.1:{port}\n")
    sys.stdout.flush()

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
