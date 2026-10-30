"""The FastAPI application. The HAL lives in its lifespan.

Opening the HAL and claiming the outputs happen at startup; at shutdown (Ctrl+C, or `SIGTERM`
from systemd, both handled by uvicorn) the HAL is closed, which applies the safe state.
"""

import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from primum_runtime import __version__
from primum_runtime.api.broadcast import StateBroadcaster
from primum_runtime.api.errors import install_error_handlers
from primum_runtime.api.routes import router
from primum_runtime.config import RuntimeConfig
from primum_runtime.control import Controller
from primum_runtime.hal import Hal, create_hal

log = logging.getLogger(__name__)

# The page and its generated assets (i18n catalogs, tokens, icons), served at "/".
UI_DIR = Path(__file__).resolve().parent.parent / "ui"

type HalFactory = Callable[[], Hal]


def create_app(config: RuntimeConfig, open_hal: HalFactory | None = None) -> FastAPI:
    """The API for ``config``. ``open_hal`` replaces the HAL ``config`` asks for (tests).

    ``app.state.stopped_safely`` becomes true once the HAL has closed without errors.
    """

    def default_hal() -> Hal:
        return create_hal(simulate=config.simulate, chip=config.chip)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        with (open_hal or default_hal)() as hal:
            controller = Controller(hal, config.outputs)
            broadcaster = StateBroadcaster()
            unsubscribe = controller.subscribe(broadcaster.publish)
            app.state.controller = controller
            app.state.broadcaster = broadcaster
            log.info("started outputs=%s simulate=%s", _describe(controller), config.simulate)
            try:
                yield
            finally:
                unsubscribe()
                broadcaster.close()
        # Only reached when closing the HAL raised nothing: every output is in its safe state.
        app.state.stopped_safely = True
        log.info("stopped outputs=%s", _describe(controller))

    app = FastAPI(title="Primum runtime", version=__version__, lifespan=lifespan)
    app.state.stopped_safely = False
    app.include_router(router)
    # Mounted last: the API's routes are matched first.
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
    install_error_handlers(app)
    return app


def _describe(controller: Controller) -> str:
    return ",".join(
        f"{output.name}:{'on' if output.on else 'off'}" for output in controller.state().outputs
    )
