# Tools

Developer scripts. Common tasks are exposed through the `justfile`.

- `gen_tokens.py`: generates `design/tokens/tokens.css` from `design/tokens/tokens.json`
  (`just gen`; `--check` in CI).
- `gen_ui_assets.py`: copies `i18n/*.json`, `tokens.css`, the icons and the logo into
  `packages/runtime/src/primum_runtime/ui/generated/`, so the installed runtime serves them
  (`just gen`; `--check` in CI).
- `pi.sh`: works against the development Pi (block 1.4) for the `just pi-*` tasks: provision it,
  sync this working tree and restart the service, run the `hw` tests there, follow the log. The
  host comes from `PRIMUM_PI_HOST` (no default). Needs `ssh` and `rsync` on the laptop.
