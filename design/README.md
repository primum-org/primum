# Design

Primum's brand and design system. Chosen style: **Brass automaton · compact**
(*Autómata de latón · compacto*): the *Primum Mobile* desk planetarium — ivory paper and ink in
light mode, ebony and brass in dark mode — with near-square corners, 1 px rules instead of soft
shadows and desktop density. Touch surfaces (local web on a phone, kiosk, welcome wizards) keep
large controls. See [decision 0007](../docs/decisions/0007-brand-and-design-tokens.md).

Source: the Claude Design system <https://claude.ai/artifact/4qZ3u7SrWZZ6gg3gTmyWV4>
(also the live identity and interface sheets in light and dark).

## Contents

| Path | What | Edit? |
|---|---|---|
| `brandbook.es.md` | The full brandbook (in Spanish, as exported): concept, logo, color, type, icons, illustration, components, screens, voice, tokens | Only to sync it with the source |
| `tokens/tokens.json` | **Design tokens: the single source** of colors, fonts, sizes, radii, spacing, shadows and motion | Yes |
| `tokens/tokens.css` | CSS custom properties generated from `tokens.json` (`just gen`) | **Never** (generated) |
| `logo/` | The symbol at 48 px and its redrawn 16 px version, in light, dark and mono (`currentColor`) | Only from the source |
| `icons/` | 56 icons on a 24 px grid, `currentColor` | Only from the source |

## Using the tokens

- Load `tokens/tokens.css`. The theme follows `prefers-color-scheme` unless
  `<html data-theme="light|dark">` is set.
- Property names follow the token path: `color.semantic.danger` → `--color-semantic-danger`,
  `font.size.md` → `--font-size-md`, `radius.md` → `--radius-md`, `space.3` → `--space-3`.
- **Never hard-code a HEX value, font or size** in the UI: use the properties.
- After editing `tokens.json`, run `just gen` and commit both files. CI fails if `tokens.css` is
  out of date.

## Rules that the UI must keep

- **Reserved semantic colors** (`danger`, `warning`, `success`, `running`, `offline`, `safe`,
  `proposal`) are used only for their meaning, and always with an icon **and** a word.
  `offline` (local mode) is normal, not an alarm. An AI proposal always has a dashed border.
  Brass never signals a state.
- **Editor tracks** (`color-track-1` … `12`) are used only for tracks, and each track also shows
  its number, name, element icon and its own pattern (dark-mode tracks are close to the limit for
  color-blind users).
- **Type:** Fraunces (`--font-family-display`) for titles only, never below 18–19 px, never on
  buttons or fields; Instrument Sans (`--font-family-ui`) for the whole interface; DM Mono
  (`--font-family-mono`) for pins, times, networks and addresses (`Primum-7F3A`, `primum.local`).
  All three are SIL OFL 1.1.
- **Shape:** `--radius-sm` (0) blocks, alerts, chips · `--radius-md` (2 px) buttons, fields,
  badges, cards · `--radius-lg` (3 px) large panels, modals · `--radius-full` only for status
  dots, switches and the logo's astro. The panic button keeps its octagonal chamfer.
- **Density:** desktop controls 32–36 px; inside a `.touch` container nothing is below 44 px,
  transport controls are 64 px and panic 72 px. Brass focus ring: 2 px on desktop, 3 px on touch.
- **Motion:** `--motion-fast|base|slow`; respect `prefers-reduced-motion`.
- **Icons:** 24 px grid, 1.5 px stroke, butt caps, mitred joins, one solid pivot per icon,
  `currentColor`. Sizes 16, 20, 24, 32. Nothing borrowed from third-party board brands.
- **Logo:** never recolor it with a state color, rotate it, add gears or gradients, or reset the
  name in another typeface.
- **Voice:** clear, calm and precise: what happened, why, what to do. No emoji: states use an icon
  and a word. UI languages are English and Spanish only
  ([decision 0003](../docs/decisions/0003-languages.md)); the Catalan examples in the brandbook
  are not used.

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

- Logotype (symbol + "Primum") outlined to curves: the sheets set it live in Fraunces.
- App icon set (1024 → 16 px) and favicon, as described in the brandbook (§2).
- Font files (woff2, Latin + Latin Extended) bundled for offline use: phase 5.
- Icons for the project file types (`.sec`, `.auto`, `.evt`, `.prog`, `.vars`, `.hw`) and for the
  file explorer.
