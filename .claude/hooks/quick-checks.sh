#!/usr/bin/env bash
# Stop: before finishing, run types and tests if Python files changed. On failure Claude keeps working.
set -euo pipefail

# Already continuing because of this hook: do not loop forever.
[[ "$(python3 "$(dirname "$0")/_input.py" stop_hook_active)" == "True" ]] && exit 0

cd "${CLAUDE_PROJECT_DIR:-$PWD}"
git status --porcelain -- '*.py' 'pyproject.toml' | grep -q . || exit 0

if ! output=$(uv run --quiet pyright 2>&1); then
  echo "pyright failed. Fix the type errors before finishing:" >&2
  echo "$output" | tail -40 >&2
  exit 2
fi
if ! output=$(uv run --quiet pytest -q -x 2>&1); then
  echo "Tests failed. Fix them before finishing:" >&2
  echo "$output" | tail -40 >&2
  exit 2
fi
exit 0
