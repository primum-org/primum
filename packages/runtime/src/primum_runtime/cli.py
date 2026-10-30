"""``primum-runtime``: start the service with uvicorn.

uvicorn handles `SIGINT` and `SIGTERM` by shutting the application down, which closes the HAL
and applies the safe state (decision 0010). `SIGKILL` cannot be handled.
"""

import logging
import os
import sys
from collections.abc import Sequence

import uvicorn

from primum_runtime.api import create_app
from primum_runtime.config import parse_config
from primum_runtime.errors import PrimumError

log = logging.getLogger(__name__)

# Exit status when the service could not start, or stopped without the safe state.
EXIT_FAILED = 1


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        config = parse_config(sys.argv[1:] if argv is None else argv, os.environ)
    except PrimumError as error:
        log.error("invalid configuration: %s", error)
        return EXIT_FAILED
    app = create_app(config)
    server = uvicorn.Server(
        uvicorn.Config(app, host=config.host, port=config.port, log_config=None)
    )
    # On SIGINT or SIGTERM, uvicorn shuts the app down and then re-raises the signal, so the
    # process ends by it (what systemd expects) and never returns here; the lifespan has
    # already logged whether the safe state was applied.
    server.run()
    # Otherwise uvicorn logs a failed startup or shutdown but returns normally: the exit status
    # says whether the outputs were left in their safe state.
    stopped_safely: bool = app.state.stopped_safely
    return 0 if server.started and stopped_safely else EXIT_FAILED
