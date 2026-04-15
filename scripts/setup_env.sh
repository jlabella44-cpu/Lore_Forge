#!/usr/bin/env bash
#
# Copy shared API keys from another project's .env into Lore Forge's .env.
#
# The Anthropic / OpenAI / Dashscope keys used by Lore Forge also power
# LaunchLens / ListingJet — rather than maintain two copies, point this
# script at the other project's .env once and the three keys sync over.
#
# Usage:
#   ./scripts/setup_env.sh                             # defaults to ~/listingjet/.env
#   ./scripts/setup_env.sh /path/to/other/.env
#
# Safe to re-run. Existing Lore Forge .env values are overwritten for the
# three shared keys only; everything else (NYT, Firecrawl, affiliate tags,
# provider routing) is left alone.
set -euo pipefail

SRC="${1:-$HOME/listingjet/.env}"
DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$DEST_DIR/.env"

if [ ! -f "$SRC" ]; then
  echo "✗ source not found: $SRC" >&2
  echo "  Pass the full path as the first argument, e.g." >&2
  echo "    $0 ~/launchlens/.env" >&2
  exit 1
fi

if [ ! -f "$DEST" ]; then
  echo "  bootstrapping $DEST from .env.example"
  cp "$DEST_DIR/.env.example" "$DEST"
fi

SHARED_KEYS=(
  ANTHROPIC_API_KEY
  OPENAI_API_KEY
  DASHSCOPE_API_KEY
)

copied=0
missing=()
for key in "${SHARED_KEYS[@]}"; do
  val=$(grep -E "^${key}=" "$SRC" 2>/dev/null | head -1 | cut -d= -f2- || true)
  if [ -n "${val:-}" ]; then
    awk -v k="$key" -v v="$val" '
      BEGIN { FS = OFS = "="; done = 0 }
      $1 == k { print k "=" v; done = 1; next }
      { print }
      END { if (!done) print k "=" v }
    ' "$DEST" > "$DEST.tmp"
    mv "$DEST.tmp" "$DEST"
    echo "  ✓ $key"
    copied=$((copied + 1))
  else
    missing+=("$key")
  fi
done

echo
echo "Synced $copied/${#SHARED_KEYS[@]} keys from $SRC → $DEST"
if [ "${#missing[@]}" -gt 0 ]; then
  echo "Missing in source (fill in manually): ${missing[*]}"
fi
