# Tools

Developer scripts. Common tasks are exposed through the `justfile`.

- `gen_schemas.py`: generates `core`'s view of the formats from `schemas/` into
  `packages/core/src/primum_core/generated/`: the schemas `core` validates against and a frozen
  dataclass, with its parser, for every object (`just gen`; `--check` in CI).
- `gen_tokens.py`: generates `design/tokens/tokens.css` from `design/tokens/tokens.json`
  (`just gen`; `--check` in CI).
- `gen_assets.py`: copies shared files into the packages that ship them: the board profiles
  of `boards/` and the driver manifests of `drivers/` into `primum_runtime/generated/`, and
  the catalogs of `i18n/`, the board profiles and the driver manifests into
  `primum_cli/generated/` (`just gen`; `--check` in CI).
- `gen_api.py`: writes the description of the runtime's HTTP API (OpenAPI, from its pydantic
  models) to `apps/webui/openapi.json`, which the web UI makes its TypeScript types from
  (`just gen`; `--check` in CI).
- `pi.sh`: works against the development Pi (block 1.4) for the `just pi-*` tasks: provision it,
  sync this working tree and restart the service, run the `hw` tests there, follow the log. The
  host comes from `PRIMUM_PI_HOST`, `primum-dev` by default. Needs `ssh` and `rsync` on the
  laptop, and `pnpm`: it builds the web UI before copying.
