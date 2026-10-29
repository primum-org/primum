---
paths:
  - "apps/webui/**"
---

# Web UI rules

- Vue 3 with `<script setup lang="ts">` and the Composition API; TypeScript `strict`, no `any`.
- Types come from the generated ones (from `schemas/`), never written by hand.
- Every visible string goes through i18n: English (default) and Spanish.
- Mobile first: touch targets of at least 44 px; it must work on a phone held in one hand.
- Colors, fonts and spacing come from the design tokens (`design/tokens/tokens.css`, generated
  from `tokens.json`), never hard-coded. Follow `design/README.md`.
- Semantic colors (danger, warning, success, running, offline, safe, proposal) are reserved
  for their meaning.
