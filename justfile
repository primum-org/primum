# Primum development tasks. Run `just` to list them.
# The same checks run in CI (.github/workflows/ci.yml): `just check` before pushing.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List the available tasks
default:
    @just --list

# Install or update the Python environment from uv.lock
sync:
    uv sync

# Run every test (pass extra pytest arguments after the task name)
test *args:
    uv run pytest {{args}}

# Re-run the tests every time a file is saved
watch:
    uv run ptw . --now

# Lint without changing files
lint:
    uv run ruff check
    uv run ruff format --check

# Fix lint issues and format the code
fmt:
    uv run ruff check --fix
    uv run ruff format

# Strict type checking
typecheck:
    uv run pyright

# Architecture rules (core stays pure)
arch:
    uv run lint-imports

# Regenerate generated files (design tokens CSS)
gen:
    uv run python tools/gen_tokens.py

# Fail if a generated file is out of date
gen-check:
    uv run python tools/gen_tokens.py --check

# Everything CI runs: lint, types, architecture, generated files and tests
check: lint typecheck arch gen-check test
