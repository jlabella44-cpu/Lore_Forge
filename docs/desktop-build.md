# Desktop build handoff

Status as of this commit: A1–A4 of the desktop roadmap are scaffolded.
A1 (path anchoring) and A2 (static-export) are fully validated. A3
(PyInstaller sidecar) and A4 (Tauri shell) need a local terminal with
Rust + native toolchains to produce signed installers.

## Quick start (developer loop)

On the packaging machine:

```bash
# One-time
rustup update stable
pip install -r backend/requirements.txt -r backend/requirements-build.txt
npm install                                  # root — pulls @tauri-apps/cli
npm --prefix frontend install

# Generate the icon set once from a 1024×1024 PNG (any square PNG works)
cd src-tauri && npx @tauri-apps/cli@2 icon path/to/app-icon.png && cd ..

# Dev loop — Next dev server + live Rust shell + manual sidecar
# (hot-reload isn't wired to the sidecar yet; restart `tauri dev` after
#  backend changes)
./scripts/build_sidecar.sh                   # builds + stages sidecar
npm run tauri:dev                            # launches the desktop app
```

## Producing installers

```bash
./scripts/build_sidecar.sh
npm run tauri:build
# dmg → src-tauri/target/release/bundle/dmg/
# msi → src-tauri/target/release/bundle/msi/
# .app → src-tauri/target/release/bundle/macos/
```

Tauri decides the bundle formats from the host OS: macOS → `.dmg`
+ `.app`, Windows → `.msi` + `.exe`, Linux → `.AppImage` + `.deb`. We
only target macOS and Windows per the plan.

## What still needs to happen at the terminal

1. **Generate real icons** (`src-tauri/icons/`). Without them
   `tauri build` fails. `tauri dev` runs fine without.
2. **Verify the sidecar builds under PyInstaller on macOS and Windows.**
   Import hooks sometimes miss dynamically-imported modules; if the
   packaged app fails with `ModuleNotFoundError`, add the offender to
   `hiddenimports` in `backend/sidecar.spec`.
3. **Signing + notarization** (macOS needs an Apple Developer ID and
   `xcrun notarytool`; Windows needs an Authenticode cert). Defer for
   v1 if you're OK with SmartScreen / Gatekeeper warnings.
4. **CI**: a GitHub Actions matrix (`macos-latest`, `windows-latest`)
   running `build_sidecar.sh` → `tauri build` → upload artifact. Not
   written yet — the workflow-edit permission isn't granted in this
   session.
5. **ffmpeg + Remotion (A5)**: the renderer still shells out to
   ffmpeg and `npx remotion render`. Neither is bundled. First pass
   for v1 should ship the simpler ffmpeg-only path (the plan file has
   the A5 design).
6. **Secrets UI (A6)**: provider API keys still read from `.env`.
   Needs a Settings UI that writes to the OS keychain. Not done.

## How the pieces fit

```
   ┌────────────────── Tauri shell (Rust, src-tauri/main.rs) ──────────────────┐
   │                                                                           │
   │   1. spawn sidecar (binary from PyInstaller)                              │
   │        └─ stdout: "SIDECAR_READY http://127.0.0.1:<port>"                 │
   │                                                                           │
   │   2. webview loads frontend/out/index.html  (Next.js static export)       │
   │        └─ window.__LORE_FORGE_API__ = "<sidecar url>" injected via eval   │
   │                                                                           │
   │   3. on window close → child.kill()                                       │
   │                                                                           │
   └───────────────────────────────────────────────────────────────────────────┘
```

The sidecar sets `LORE_FORGE_DESKTOP=1` before importing `app.*`, which
makes `app.paths.app_base_dir()` anchor at `~/Library/Application
Support/LoreForge/` (macOS) or `%APPDATA%\LoreForge\` (Windows). On
first launch the lifespan runs `alembic upgrade head` programmatically
via `app.migrations.run_migrations_to_head`.

## Files

- `backend/sidecar.py` — PyInstaller entry point, prints SIDECAR_READY
- `backend/sidecar.spec` — PyInstaller spec, bundles `db/` + `music/`
- `backend/requirements-build.txt` — packaging-only deps
- `backend/app/migrations.py` — programmatic alembic runner, handles
  both `db/alembic.ini` (dev) and `sys._MEIPASS/db/alembic.ini` (frozen)
- `backend/app/paths.py` — `app_base_dir()` + `resolve_default_path()`
- `src-tauri/` — Tauri v2 project (Cargo.toml, tauri.conf.json,
  src/main.rs, capabilities/)
- `scripts/build_sidecar.sh` — PyInstaller invocation + per-triple
  staging into `src-tauri/binaries/sidecar-<triple>[.exe]`
- `package.json` (repo root) — Tauri CLI devDep + scripts
