#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMON_DIR="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)"
PRIMARY_ROOT="$(dirname "$COMMON_DIR")"

if [[ -n "${GOV_PYTHON:-}" ]]; then
  PYTHON_BIN="$GOV_PYTHON"
elif [[ -x "$PRIMARY_ROOT/.code-graph/venv/bin/python3" ]]; then
  PYTHON_BIN="$PRIMARY_ROOT/.code-graph/venv/bin/python3"
else
  PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" "$ROOT/scripts/governance_docs.py" --root "$ROOT" "$@"

