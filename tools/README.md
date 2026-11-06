# Tools

Developer scripts. Common tasks are exposed through the `justfile`.

- `gen_schemas.py`: generates `core`'s view of the formats from `schemas/` into
  `packages/core/src/primum_core/generated/`: the schemas `core` validates against and a frozen
  dataclass, with its parser, for every object (`just gen`; `--check` in CI).
- `gen_tokens.py`: generates `design/tokens/tokens.css` from `design/tokens/tokens.json`
  (`just gen`; `--check` in CI).
- `gen_assets.py`: copies shared files into the packages that ship them: `i18n/*.json`,
  `tokens.css`, the icons and the logo into `primum_runtime/ui/generated/` (the page serves
  them), the board profiles of `boards/` into `primum_runtime/generated/boards/`, and the
  catalogs into `primum_cli/generated/i18n/` (`just gen`; `--check` in CI).
- `pi.sh`: works against the development Pi (block 1.4) for the `just pi-*` tasks: provision it,
  sync this working tree and restart the service, run the `hw` tests there, follow the log. The
  host comes from `PRIMUM_PI_HOST`, `primum-dev` by default. Needs `ssh` and `rsync` on the
  laptop.
