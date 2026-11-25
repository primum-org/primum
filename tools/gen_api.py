"""Write the description of the runtime's HTTP API where the web UI takes its types from.

The API's bodies are pydantic models (``primum_runtime.api.models``): they are the source.
This writes what FastAPI derives from them (OpenAPI) to ``apps/webui/openapi.json``, and the
web UI generates its TypeScript types from that file when it is built or checked. The
service itself serves no description of its API (``docs/specs/pairing.md``).

    uv run just gen         # write it
    uv run just gen-check   # fail if it is out of date (part of `just check`)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from primum_runtime.api import create_app
from primum_runtime.config import parse_config

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "apps" / "webui" / "openapi.json"


def description() -> str:
    """The API's description, as it is written: the same bytes for the same models."""
    # Any configuration will do: the routes and their bodies do not depend on it.
    logging.disable(logging.WARNING)  # it warns that pairing is off: not news here
    app = create_app(parse_config(["--simulate", "--no-pairing"], {}))
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the description of the runtime's HTTP API.")
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = parser.parse_args()
    wanted = description()
    if not args.check:
        TARGET.write_text(wanted, encoding="utf-8")
        return 0
    if TARGET.is_file() and TARGET.read_text(encoding="utf-8") == wanted:
        return 0
    sys.stderr.write(f"{TARGET.relative_to(ROOT)} is out of date: run `just gen`\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
