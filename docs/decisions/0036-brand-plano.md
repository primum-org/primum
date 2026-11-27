# 0036. Brand: "Plano" replaces "Brass automaton · compact"

- Status: Accepted
- Date: 2026-11-27
- Supersedes: the brand chosen in [0007](0007-brand-and-design-tokens.md) (its token rules stay)

## Context
"Brass automaton · compact" (0007) gave Primum a warm, ornamental look: ivory and brass, a serif
for titles, round pivots. A second brandbook direction, **"Plano"**, was drawn with its own logo:
a technical drawing — dot grid, 1 px rules, numbered mono labels — with a single blue for what
can be pressed or is running. It reads closer to what Primum is (a precise tool that coordinates
boards, pins and scenes) and is calmer in the dense screens to come (multi-track editor, trace).

## Decision
- The brand is **"Plano"** (`design/brandbook.es.html`): cold white and navy ink in light mode,
  deep navy in dark mode, signal blue `brand.primary` as the only action color (also focus and
  "running"), square corners everywhere, Geist and Geist Mono, a pixel face for large figures.
- The logo is the new symbol: thick ring, thin axis to 1:30, square pivot and square blue astro
  with an air gap. It replaces the brass planetarium in `design/logo/`.
- Token **names** stay as agreed in 0007, so adopting the brand is changing values in
  `tokens.json`. The brand adds a few tokens it needs: `font.family.pixel`, `font.size.display`,
  `color.surface.sunken`, `color.border.default|strong` and `color.text.body`.
- `design/tokens/tokens.json` is still the single source; `tokens.css` is still generated.
- The brandbook is kept as the self-contained HTML page it was drawn as, in Spanish; the old
  `brandbook.es.md` is removed. `design/README.md` summarises the rules in English.

## Alternatives considered
- Keeping "Brass automaton": warmer for non-technical users, but the brass and the serif fight
  with the density of the editor, and the ornament dates quickly.
- Keeping the old logo with the new colors: the round brass planetarium does not belong to a
  square, blueprint-like system.

## Consequences
- Every UI follows the new rules in `design/README.md`: one action color, radius 0, mono
  uppercase labels and buttons, blue focus ring and current tab.
- The 56 icons keep their drawings but carry the square 2 × 2 pivot; a full redraw is pending.
- The brandbook page loads its fonts from Google Fonts when opened; the UI never does: the fonts
  are to be bundled as woff2 for offline use (phase 5), and fall back to system faces meanwhile.
