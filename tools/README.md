# Tools

Developer scripts. Common tasks are exposed through the `justfile`.

- `gen_tokens.py`: generates `design/tokens/tokens.css` from `design/tokens/tokens.json`
  (`just gen`; `--check` in CI).
- `gen_ui_assets.py`: copies `i18n/*.json`, `tokens.css`, the icons and the logo into
  `packages/runtime/src/primum_runtime/ui/generated/`, so the installed runtime serves them
  (`just gen`; `--check` in CI).
- Coming in block 1.4: syncing the code to the development Pi and restarting the service.
