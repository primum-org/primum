# Decisions

One short note per decision that others will rely on (an ADR: architecture decision record).
They explain *why* things are the way they are, so nobody (human or AI) undoes them by accident.

To add one: copy the template below into `NNNN-short-title.md` with the next number.
A decision is never edited to say something else: write a new one that supersedes it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-python-for-core-and-runtime.md) | Python for `core` and the Linux runtime; TypeScript for the UI | Accepted |
| [0002](0002-apache-2-license.md) | Apache-2.0 license | Accepted |
| [0003](0003-languages.md) | English for code and docs; UI in English (default) and Spanish | Accepted |
| [0004](0004-project-workspace-and-file-types.md) | A project is a workspace of files with internal extensions; `.primum` to save it | Accepted |
| [0005](0005-variable-scopes.md) | Variables are scoped by folder; redefinition is an error | Accepted |
| [0006](0006-events-and-output-arbitration.md) | Events come from outside only; outputs are arbitrated by priority layers | Accepted |
| [0007](0007-brand-and-design-tokens.md) | Brand "Brass automaton · compact"; design tokens are the single source | Accepted |
| [0008](0008-json-schema-as-the-source-of-formats.md) | Hand-written JSON Schema is the source of every format | Accepted |
| [0009](0009-error-codes-and-message-catalogs.md) | Errors are codes with parameters; text lives in translation catalogs | Accepted |
| [0010](0010-hal-from-phase-1-and-gpiod.md) | The HAL exists from phase 1; gpiod is a Linux-only dependency behind it | Accepted |

## Template

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
What problem or question forced a decision.

## Decision
What we decided, stated plainly.

## Alternatives considered
What else was on the table and why it lost.

## Consequences
What this makes easier, what it makes harder, what must now be true.
```
