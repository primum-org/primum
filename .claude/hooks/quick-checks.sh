#!/usr/bin/env bash
# Stop: before finishing, run the fast checks if relevant files changed. On failure Claude keeps working.
#
# The Edit/Write hooks (protect-generated.sh, format.sh) do not see edits made through Bash
# (sed, heredocs, cp...). This hook runs on every stop, so it also catches those: lint, format,
# stale generated files, types and tests. CI (`just check`) remains the final net.
set -euo pipefail

# Already continuing because of this hook: do not loop forever.
[[ "$(python3 "$(dirname "$0")/_input.py" stop_hook_active)" == "True" ]] && exit 0

cd "${CLAUDE_PROJECT_DIR:-$PWD}"
git status --porcelain -- '*.py' 'pyproject.toml' 'uv.lock' 'design/tokens/' | grep -q . || exit 0

run() {
  local what=$1
  shift
  if ! output=$("$@" 2>&1); then
    echo "$what failed. Fix it before finishing:" >&2
    echo "$output" | tail -40 >&2
    exit 2
  fi
}

run "ruff check" uv run --quiet ruff check
run "ruff format --check (run: uv run just fmt)" uv run --quiet ruff format --check
run "Generated files check (run: uv run just gen)" uv run --quiet python tools/gen_tokens.py --check
run "pyright" uv run --quiet pyright
run "Tests" uv run --quiet pytest -q -x
exit 0
