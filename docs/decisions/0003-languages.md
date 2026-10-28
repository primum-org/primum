# 0003. English for code and docs; UI in English (default) and Spanish

- Status: Accepted
- Date: 2026-10-28

## Context
The project is open source and aims at contributors beyond Spain, while its first users
speak Spanish.

## Decision
- Code, identifiers, comments, commit messages and everything in `docs/` are in **English**.
- The UI is translated through i18n. **English is the default locale; Spanish is the second.**
  No other locale for now.
- `docs/glossary.md` maps each English term to the Spanish one shown in the UI.

## Alternatives considered
- Spanish docs: easier for the author, but excludes most potential contributors.
- Catalan as a third UI locale: left out for now to keep translation work small.

## Consequences
- No user-visible string is hard-coded; every string has an English and a Spanish entry.
- Layouts must cope with text of different lengths.
