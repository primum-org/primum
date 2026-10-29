# Tools

Developer scripts. Common tasks are exposed through the `justfile`.

- `gen_tokens.py`: generates `design/tokens/tokens.css` from `design/tokens/tokens.json`
  (`just gen`; `--check` in CI).
- Coming in phase 1: syncing the code to the development Pi and restarting the service.
