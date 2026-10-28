# Contributing to Primum

Thanks for your interest! Primum is in early development, so the best way to help right now is
to open an issue with ideas, use cases or questions.

## Setup

1. Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/)
   (`uv tool install rust-just` works too).
2. `just sync` to install the environment.
3. `uv run pre-commit install` to run the formatters on every commit.

## Workflow

1. Create a branch from `main`.
2. Make a focused change. Read `CLAUDE.md` and the rules in `.claude/rules/`: they apply to
   humans too.
3. Add or update tests. Update `docs/specs/` if behaviour changes, `CHANGELOG.md` if users
   would notice, and add a note in `docs/decisions/` for design choices.
4. Run `just check`. It runs exactly what CI runs.
5. Open a pull request using the template.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `feat(core): …`,
`fix(runtime): …`, `docs: …`, `chore: …`, `test: …`, `refactor: …`.

## Code style

- English for code, comments and docs.
- Python 3.13, strict typing, `ruff` for lint and format.
- `primum-core` stays pure: no hardware, network or storage (checked by `just arch`).
- Safety first: no driver without a safe state, limits and tests.

## Code of conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
