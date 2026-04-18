#!/usr/bin/env bash
# Build the PyInstaller sidecar and stage it for Tauri.
#
# Tauri's `externalBin` resolves `binaries/sidecar` to
# `binaries/sidecar-<target-triple>[.exe]` per platform — e.g.
# `binaries/sidecar-x86_64-apple-darwin` on Intel Mac. This script
# detects the host triple, runs PyInstaller, and copies the output into
# `src-tauri/binaries/` under the right name.
#
# Prerequisites on the packaging machine:
#   python >= 3.11 with `pip install -r backend/requirements.txt -r backend/requirements-build.txt`
#   rustup target add <triple> (for cross-compilation, which we don't
#     do here — each host builds its own)
#
# Usage:
#   ./scripts/build_sidecar.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Host target-triple as Tauri expects it. `rustc -vV` prints it under
# `host: ...`. Fall back to `uname` if rustc isn't installed — dev-only
# convenience so you can build the sidecar without Rust.
if command -v rustc >/dev/null 2>&1; then
  TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"
else
  case "$(uname -sm)" in
    "Darwin arm64")  TRIPLE="aarch64-apple-darwin" ;;
    "Darwin x86_64") TRIPLE="x86_64-apple-darwin" ;;
    "Linux x86_64")  TRIPLE="x86_64-unknown-linux-gnu" ;;
    "MINGW"*|"MSYS"*|"CYGWIN"*) TRIPLE="x86_64-pc-windows-msvc" ;;
    *) echo "unknown platform $(uname -sm); install rustup" >&2; exit 1 ;;
  esac
fi

echo "Building sidecar for $TRIPLE"
pyinstaller --clean --noconfirm backend/sidecar.spec

mkdir -p src-tauri/binaries
SRC="dist/sidecar"
EXT=""
if [[ "$TRIPLE" == *"windows"* ]]; then
  SRC="dist/sidecar.exe"
  EXT=".exe"
fi

DEST="src-tauri/binaries/sidecar-${TRIPLE}${EXT}"
cp "$SRC" "$DEST"
echo "Staged sidecar at $DEST"
