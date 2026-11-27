"""The FastAPI application. The HAL lives in its lifespan, and so does the watch on its
input events: the event loop reads them when the HAL's descriptor says there are some.
Under systemd it also says when it is ready and, while it runs, that it is alive.

Opening the HAL and claiming the outputs happen at startup; at shutdown (Ctrl+C, or `SIGTERM`
from systemd, both handled by uvicorn) the HAL is closed, which applies the safe state.
"""

import asyncio
import itertools
import logging
import os
import time
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import override

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from primum_runtime import __version__, systemd
from primum_runtime.api.broadcast import StateBroadcaster
from primum_runtime.api.deploy import Deployment, HalFactory, Parts
from primum_runtime.api.errors import install_error_handlers
from primum_runtime.api.pairing import router as pairing_router
from primum_runtime.api.routes import BEAT_S, router
from primum_runtime.config import RuntimeConfig
from primum_runtime.control import Controller, Wall
from primum_runtime.hal import Hal, create_hal
from primum_runtime.pairing import Pairing
from primum_runtime.trace import Trace

log = logging.getLogger(__name__)

# The web UI (``apps/webui``), served at "/". It is built into the package when it is
# deployed and is not in the repository: a service without it has its API and no page.
WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"


def create_app(
    config: RuntimeConfig,
    open_hal: HalFactory | None = None,
    env: Mapping[str, str] | None = None,
    wall: Wall | None = None,
    beat_s: float = BEAT_S,
) -> FastAPI:
    """The API for ``config``. ``open_hal`` replaces the HAL ``config`` asks for (tests): it
    is called for a new HAL each time what runs changes; ``env`` is where systemd says how
    to reach it (the process's environment unless given); ``wall`` replaces the system's
    clock, for the schedules (tests); ``beat_s`` is how long the WebSocket of the state
    stays silent at most (tests make it short).

    ``app.state.stopped_safely`` becomes true once the HAL has closed without errors.
    ``app.state.deployment`` is what runs (``api.deploy``); its controller changes when a
    package is activated, so nothing keeps it across requests.
    """
    notify = systemd.notifier(os.environ if env is None else env)
    watchdog_interval_s = systemd.watchdog_interval_s(os.environ if env is None else env)

    def default_hal() -> Hal:
        return create_hal(simulate=config.simulate, board=config.board)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        broadcaster = StateBroadcaster()
        parts = Parts(
            config=config,
            open_hal=open_hal or default_hal,
            wall=wall or systemd.trusted_time(trust=config.trust_clock),
            loop=asyncio.get_running_loop(),
            broadcaster=broadcaster,
            trace=Trace(),
            origin=time.monotonic(),
            clock=time.monotonic,
            revisions=itertools.count(1),
        )
        deployment = Deployment(parts)
        app.state.deployment = deployment
        app.state.broadcaster = broadcaster
        app.state.trace = parts.trace
        # The beats come from this loop: if it is stuck, systemd stops hearing them.
        watchdog = None
        if watchdog_interval_s is not None:
            beats = systemd.feed_watchdog(notify, watchdog_interval_s, asyncio.sleep)
            watchdog = asyncio.create_task(beats)
        log.info(
            "started outputs=%s simulate=%s", _describe(deployment.controller), config.simulate
        )
        notify(systemd.READY)
        try:
            yield
        finally:
            notify(systemd.STOPPING)
            if watchdog is not None:
                watchdog.cancel()
            try:
                deployment.stop()
            finally:
                broadcaster.close()
        # Only reached when closing the HAL raised nothing: every output is in its safe state
        # and released.
        app.state.stopped_safely = True
        log.info("stopped outputs=%s", _describe(deployment.controller))

    # It describes itself to nobody: FastAPI's own pages (/docs, /openapi.json) would be
    # routes outside pairing.
    app = FastAPI(
        title="Primum runtime",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.stopped_safely = False
    app.state.beat_s = beat_s
    app.state.pairing = Pairing(config.data_dir, time.monotonic) if config.pairing else None
    if not config.pairing:
        log.warning("pairing is off: whoever reaches this service commands it")
    app.include_router(pairing_router)
    app.include_router(router)
    # Mounted last: the API's routes are matched first, and the web UI takes every other path.
    if (WEBUI_DIR / "index.html").is_file():
        app.mount("/", _WebUi(directory=WEBUI_DIR, html=True), name="webui")
    else:
        log.warning("the web UI is not built (`just ui-build`): this service has no page")
    install_error_handlers(app)
    return app


class _WebUi(StaticFiles):
    """The built web UI. Its index is asked for again each time: after a deployment it
    names other files, and one a browser kept would ask for files that are gone. The files
    have their content in their name, and are a browser's to keep."""

    @override
    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        if Path(full_path).suffix == ".html":
            response.headers["Cache-Control"] = "no-cache"
        return response


def _describe(controller: Controller) -> str:
    return ",".join(
        f"{_named(output.name, output.id)}:{'on' if output.on else 'off'}"
        for output in controller.state().outputs
    )


def _named(name: str, id_: str) -> str:
    """An element in a log: its name, and its id when it has one of its own, since two
    elements of a package may share a name."""
    return name if id_ == name else f"{name} ({id_})"
