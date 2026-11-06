# primum-cli

Primum's command line. It reads a project folder and gives it to `primum-core`, which does no
I/O itself, then writes what `core` reports in the user's language.

    uv run primum validate examples/minimal
    uv run primum validate my-project --lang es
    uv run primum validate my-project --json      # for scripts, CI and AI assistants
    uv run primum validate my-project --strict    # warnings fail too

Exit status: 0 the project is valid, 1 it has problems, 2 the command could not run (a wrong
option, or a folder that cannot be read).

Messages come from the catalogs in `i18n/` (decision 0009), copied into the package by
`just gen` (`primum_cli/generated/i18n/`).
