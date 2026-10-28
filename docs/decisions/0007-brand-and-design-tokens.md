# 0007. Brand: "Brass automaton · compact", with design tokens as the single source

- Status: Accepted
- Date: 2026-10-28

## Context
Several brandbook directions were explored in Claude Design. The UI (web UI on the board, later
Primum Studio) needs one visual language and one source of colors, fonts and sizes, in the same
way `schemas/` is the single source of the data formats.

## Decision
- The brand is **"Brass automaton · compact"** (*Autómata de latón · compacto*): ivory and ink in
  light mode, ebony and brass in dark mode; near-square corners and desktop density, with large
  touch controls on phones and kiosks.
- Everything lives in `design/`: the brandbook, the logo, the icons and the tokens.
- **`design/tokens/tokens.json` is the single source** of colors, fonts, font sizes, radii,
  spacing, shadows and motion. `design/tokens/tokens.css` is generated from it by
  `tools/gen_tokens.py` (`just gen`), is never edited by hand and is checked in CI.
- CSS custom properties are named after the token path (`--color-semantic-danger`).
- The brandbook stays in Spanish, as exported from Claude Design; `design/README.md` summarises the
  rules in English.

## Alternatives considered
- The rounded "Primum" variant: friendlier on first contact, but less information per screen in
  the multi-track editor, which is where users spend their time.
- Keeping Claude Design's list-shaped `tokens.json`: it is tied to that tool; the nested format
  matches the token names agreed for the platform and maps directly to CSS properties.

## Consequences
- UI code never hard-codes colors, fonts or sizes.
- Reserved semantic colors and track colors are used only for their meaning, always with an icon
  and a word (or number and pattern for tracks).
- The brandbook's Catalan examples are not used: UI languages are English and Spanish
  (decision 0003).
- A change to the brand is made in Claude Design first and then synced into `design/`.
