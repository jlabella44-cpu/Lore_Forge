#!/usr/bin/env bash
# Reports Lore Forge environment readiness at session start so Claude knows
# what's installed/missing without probing. Output is JSON with
# additionalContext injected into the model's context.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 0

branch=$(git branch --show-current 2>/dev/null || echo 'unknown')
dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
ahead_behind=$(git rev-list --left-right --count '@{upstream}...HEAD' 2>/dev/null || echo '? ?')

check() { [ -e "$1" ] && echo "ok" || echo "MISSING — $2"; }

backend_venv=$(check backend/.venv "cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt")
frontend_deps=$(check frontend/node_modules "cd frontend && npm install")
remotion_deps=$(check remotion/node_modules "cd remotion && npm install")
env_file=$(check .env "cp .env.example .env")
frontend_env=$(check frontend/.env.local "cp frontend/.env.local.example frontend/.env.local")

context=$(cat <<EOF
## Lore Forge session status

Branch: $branch  ·  Uncommitted: $dirty file(s)  ·  upstream behind/ahead: $ahead_behind

Environment:
- backend venv:  $backend_venv
- frontend deps: $frontend_deps
- remotion deps: $remotion_deps
- .env:          $env_file
- frontend/.env.local: $frontend_env

Bash timeout defaults for this project: 60s default, 300s max (set via .claude/settings.json env). Pass an explicit timeout on long-running Bash calls. Prefer run_in_background for servers, migrations, and test suites so the session isn't blocked if they hang.
EOF
)

jq -Rs --arg ctx "$context" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}' <<< ""
