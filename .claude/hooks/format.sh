#!/usr/bin/env bash
# PostToolUse (Edit|Write): formats the edited Python file and reports lint errors back to Claude.
set -euo pipefail

file=$(python3 "$(dirname "$0")/_input.py" tool_input.file_path)
[[ "$file" == *.py && -f "$file" ]] || exit 0

cd "${CLAUDE_PROJECT_DIR:-$PWD}"
if ! output=$(uv run --quiet ruff format "$file" 2>&1); then
  echo "ruff format could not format $file (syntax error?):" >&2
  echo "$output" >&2
  exit 2
fi
# Unused imports and variables are normal between two edits (added now, used in the next one):
# ignore them here so ruff neither deletes them nor complains. The Stop hook and CI catch the
# ones still unused at the end.
if ! output=$(uv run --quiet ruff check --fix --extend-ignore F401,F841 "$file" 2>&1); then
  echo "ruff found problems in $file that it could not fix:" >&2
  echo "$output" >&2
  exit 2
fi
exit 0
