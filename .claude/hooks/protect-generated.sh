#!/usr/bin/env bash
# PreToolUse (Edit|Write): generated files are rebuilt from their source, never edited by hand.
set -euo pipefail

file=$(python3 "$(dirname "$0")/_input.py" tool_input.file_path)
rel=${file#"${CLAUDE_PROJECT_DIR:-$PWD}/"}

case "$rel" in
  */generated/* | docs/reference/* | design/tokens/tokens.css | uv.lock | pnpm-lock.yaml)
    echo "Blocked: '$rel' is generated. Change its source (schemas/, boards/, design/tokens/tokens.json, pyproject.toml, package.json) and regenerate it (its generator task, uv lock or pnpm install) instead of editing it." >&2
    exit 2
    ;;
esac
exit 0
