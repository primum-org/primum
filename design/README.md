# Design

Primum's brand and design system. Chosen style: **Plano** (brandbook v2): a technical drawing
that moves — cold white paper and navy ink in light mode, deep navy in dark mode, a single
signal blue for what can be pressed or is running, 1 px rules instead of shadows, square corners
everywhere, numbered mono labels and a dot grid for canvases. Touch surfaces (local web on a
phone, kiosk, welcome wizards) keep large controls. See
[decision 0036](../docs/decisions/0036-brand-plano.md), which supersedes 0007's brand (the token
rules of 0007 still hold).

## Contents

| Path | What | Edit? |
|---|---|---|
| `brandbook.es.html` | The full brandbook (in Spanish, a self-contained page; open it in a browser): concept, logo, color, type, grid and shape, icons, components, screens, voice, tokens | Only to sync it with the source |
| `tokens/tokens.json` | **Design tokens: the single source** of colors, fonts, sizes, radii, spacing, shadows and motion | Yes |
| `tokens/tokens.css` | CSS custom properties generated from `tokens.json` (`just gen`) | **Never** (generated) |
| `logo/` | `primum-favicon.svg` (the 16 px app icon: navy square, white ring, blue astro, the same in light and dark), and the symbol at 48 px and its redrawn 16 px version (no axis, 6 px astro), in light, dark and mono (`currentColor`; the astro has `class="astro"` so the UI can color it) | Only from the source |
| `icons/` | 56 icons on a 24 px grid, `currentColor`, drawn in the Plano style (all shown in the brandbook, §006) | Only with the brandbook |
| `fonts/` | Geist, Geist Mono and Pixelify Sans as variable woff2 (Latin + Latin Extended), `fonts.css` with their `@font-face`, and their SIL OFL 1.1 licenses | Only to update the fonts |

## Using the tokens

- Load `fonts/fonts.css` before `tokens/tokens.css`: it declares the families the tokens name,
  from the bundled files, so nothing is fetched from the Internet.

- Load `tokens/tokens.css`. The theme follows `prefers-color-scheme` unless
  `<html data-theme="light|dark">` is set.
- `color.neutral.*` is an **absolute** scale, identical in light and dark: it does not follow the
  theme. For anything that must adapt (backgrounds, text, borders) use `color.surface.*` and
  `color.text.*`; use `neutral` only where a fixed value is meant (e.g. text on a track block).
- Sizes (`size.*`) follow the brandbook's density table: `--size-touch-target` (44 px),
  `--size-control-{sm,md,touch}`, `--size-row-{md,touch}`, `--size-transport-{md,touch}`,
  `--size-panic-touch` and its chamfer, `--size-icon-{16,20,24,32}`, `--size-focus-ring-{md,touch}`,
  `--size-rule-{md,strong}` and `--size-content` (the width of a single-column page).
- Property names follow the token path: `color.semantic.danger` → `--color-semantic-danger`,
  `font.size.md` → `--font-size-md`, `radius.md` → `--radius-md`, `space.3` → `--space-3`.
- **Never hard-code a HEX value, font or size** in the UI: use the properties.
- After editing `tokens.json`, run `just gen` and commit both files. CI fails if `tokens.css` is
  out of date.

## Rules that the UI must keep

- **One action color.** `brand.primary` (signal blue) marks the main action, focus, the current
  tab and "running". `brand.secondary` is the navy ink of titles, the logo and strong text.
  `brand.accent` is the pale blue tint behind a highlighted row. Everything else is ink and rules.
- **Reserved semantic colors** (`danger`, `warning`, `success`, `running`, `offline`, `safe`,
  `proposal`) are used only for their meaning, and always with an icon **and** a word.
  `offline` (local mode) is normal, not an alarm. An AI proposal always has a dashed border.
  `running` shares the signal blue.
- **Surfaces and rules:** `surface.base` (paper), `surface.raised` (cards, bars), `surface.sunken`
  (hover, switch tracks), `surface.overlay`. Borders are `border.default` (rules, dividers, grid)
  and `border.strong` (fields, controls). Shadows are 1 px rings, never soft.
- **Editor tracks** (`color-track-1` … `12`) are used only for tracks, and each track also shows
  its number, name, element icon and a hatch on the heel of its blocks.
- **Type:** Geist (`--font-family-ui`, also `--font-family-display`) for everything; titles in
  500 with −3.5 % letter spacing. Geist Mono (`--font-family-mono`) for pins, times, networks and
  addresses (`Primum-7F3A`, `primum.local`) and for uppercase labels and buttons. A pixel face
  (`--font-family-pixel`, Pixelify Sans) only for large figures: pairing code, counters, kiosk
  time. Uppercase only in mono labels and buttons. All are SIL OFL 1.1.
- **Shape:** radius 0 everywhere (`--radius-sm|md|lg`). Status dots are 7 px squares; the panic
  button keeps its octagonal chamfer. `--radius-full` is no longer used by the UI.
- **Density:** desktop controls 28–36 px, rows 40; inside a `.touch` container nothing is below
  44 px, transport controls are 64 px and panic 72 px. Blue focus ring: 2 px on desktop, 3 px on
  touch.
- **Buttons:** primary is a solid blue block; secondary a 1 px ink rule; tertiary an underlined
  mono link with ↗; panic red with the chamfer, never disabled; disabled has a dashed border.
- **Panic in dark mode:** its word is `text.inverse` (navy) on the coral `semantic.danger`, not
  the white the brandbook draws: white on that coral is about 3:1, below the 4.5:1 for text;
  navy is about 6:1.
- **Disabled:** dashed border and secondary text, never opacity, for buttons, fields, switches
  and sliders.
- **Motion:** `--motion-fast|base|slow` (100 / 180 / 320 ms), linear or stepped; striped bars
  for progress; respect `prefers-reduced-motion`.
- **Icons:** 24 px grid, 1.5 px stroke, butt caps, mitred joins, one solid **2 × 2 pixel** per
  icon where the part turns, acts or is measured, `currentColor`. Sizes 16, 20, 24, 32.
- **Logo:** symbol (thick ring, thin axis pointing to 1:30, square pivot, square astro in signal
  blue with an air gap) + "Primum" in Geist 600, −4.5 %. Products add their name in Geist 300
  grey. Never rotate it, tint it with a state color, reset the name in another typeface, or add
  shadows or gradients. Minimum: logotype 88 px wide, symbol 16 px.
- **Voice:** clear, calm and precise: what happened, why, what to do. No emoji: states use an icon
  and a word. UI languages are English and Spanish only
  ([decision 0003](../docs/decisions/0003-languages.md)).

## Icon groups

- `i-*` **domain:** boards (`i-hub`, `i-node`, `i-sat`), elements (`i-led`, `i-bulb`, `i-motor`,
  `i-servo`, `i-pir`, `i-button`, `i-dist`, `i-temp`, `i-speaker`, `i-dmx`), actions (`i-play`,
  `i-playf`, `i-pause`, `i-pausef`, `i-stop`, `i-panic`, `i-test`, `i-deploy`) and connections
  (`i-wifi`, `i-usb`, `i-radio`, `i-bus`).
- `s-*` **status:** `s-warn`, `s-ok`, `s-run`, `s-ring`, `s-play`, `s-local`, `s-safe`, `s-spark`,
  `s-info`.
- `u-*` **interface:** navigation and common actions (`u-plus`, `u-x`, `u-check`, `u-seq`,
  `u-rule`, `u-board`, `u-sim`, `u-gear`…).

## Still to produce

- Logotype (symbol + "Primum") outlined to curves: the brandbook sets it live in Geist.
- App icon set (1024 → 180 px: navy square, white ring, blue astro), as described in the
  brandbook (§2). The 16 px one exists: `logo/primum-favicon.svg`, the web UI's favicon.
- Tokens for font weights, line heights and letter spacing: the brandbook gives them per size
  (display 56/1.0 … xs 12/1.4); the web UI writes the few it uses in its own CSS, with a note.
- Icons for the project file types (`.sec`, `.auto`, `.evt`, `.sched`, `.vars`, `.hw`) and for the
  file explorer.
