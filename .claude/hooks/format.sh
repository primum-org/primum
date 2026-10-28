#!/usr/bin/env bash
# PostToolUse (Edit|Write): formats the edited Python file and reports lint errors back to Claude.
set -euo pipefail

file=$(python3 "$(dirname "$0")/_input.py" tool_input.file_path)
[[ "$file" == *.py && -f "$file" ]] || exit 0

cd "${CLAUDE_PROJECT_DIR:-$PWD}"
uv run --quiet ruff format "$file" >/dev/null 2>&1 || true
if ! output=$(uv run --quiet ruff check --fix "$file" 2>&1); then
  echo "ruff found problems in $file that it could not fix:" >&2
  echo "$output" >&2
  exit 2
fi
exit 0
