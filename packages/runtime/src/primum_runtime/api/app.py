"""The FastAPI application. The HAL lives in its lifespan, and so does the watch on its
input events: the event loop reads them when the HAL's descriptor says there are some.
Under systemd it also says when it is ready and, while it runs, that it is alive.

Opening the HAL and claiming the outputs happen at startup; at shutdown (Ctrl+C, or `SIGTERM`
from systemd, both handled by uvicorn) the HAL is closed, which applies the safe state.
"""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from primum_runtime import __version__, declared, systemd
from primum_runtime.api.broadcast import StateBroadcaster
from primum_runtime.api.errors import install_error_handlers
from primum_runtime.api.expiry import ExpiryTimer
from primum_runtime.api.routes import router
from primum_runtime.config import RuntimeConfig
from primum_runtime.control import Controller, Wall
from primum_runtime.drivers import load_manifests
from primum_runtime.hal import Claim, Hal, create_hal

log = logging.getLogger(__name__)

# The page and its generated assets (i18n catalogs, tokens, icons), served at "/".
UI_DIR = Path(__file__).resolve().parent.parent / "ui"

type HalFactory = Callable[[], Hal]


def create_app(
    config: RuntimeConfig,
    open_hal: HalFactory | None = None,
    env: Mapping[str, str] | None = None,
    wall: Wall | None = None,
) -> FastAPI:
    """The API for ``config``. ``open_hal`` replaces the HAL ``config`` asks for (tests);
    ``env`` is where systemd says how to reach it (the process's environment unless given);
    ``wall`` replaces the system's clock, for the schedules (tests).

    ``app.state.stopped_safely`` becomes true once the HAL has closed without errors.
    """
    notify = systemd.notifier(os.environ if env is None else env)
    watchdog_interval_s = systemd.watchdog_interval_s(os.environ if env is None else env)

    def default_hal() -> Hal:
        return create_hal(simulate=config.simulate, board=config.board)

    declarations: list[Claim] = []  # what this service declared: one claim, or none yet

    def declare(claim: Claim) -> None:
        declared.write(config.data_dir, declared.Declaration.of(config.board.model, claim))
        declarations.append(claim)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        with (open_hal or default_hal)() as hal:
            # A real service declares what it claims before it claims it, so that primum-safe
            # can make it safe if this process dies. A simulated one has nothing to make safe.
            before_claim = None if config.simulate else declare
            try:
                controller = Controller(
                    hal,
                    config.elements,
                    load_manifests(),
                    config.limits,
                    before_claim,
                    package=config.package,
                    wall=wall or _system_time(config),
                )
            except Exception:
                # A claim that fails leaves nothing claimed: what was declared for it names
                # outputs nobody holds (a pin the board lacks, say), and primum-safe would
                # fail on it at every stop.
                if declarations:
                    declared.remove(config.data_dir)
                raise
            broadcaster = StateBroadcaster()
            unsubscribe = controller.subscribe(broadcaster.publish)
            app.state.controller = controller
            app.state.broadcaster = broadcaster
            # Input changes are read when the HAL says there are some: no thread, no polling.
            # Without inputs there is nothing to watch.
            loop = asyncio.get_running_loop()
            # Tests that expire on their own, and the sequences in their time.
            expiry = ExpiryTimer(controller, loop.call_later)
            events_fd = controller.events_fd()
            if events_fd is not None:
                loop.add_reader(events_fd, _read_inputs, loop, events_fd, controller)
            # The beats come from this loop: if it is stuck, systemd stops hearing them.
            watchdog = None
            if watchdog_interval_s is not None:
                beats = systemd.feed_watchdog(notify, watchdog_interval_s, asyncio.sleep)
                watchdog = asyncio.create_task(beats)
            log.info("started outputs=%s simulate=%s", _describe(controller), config.simulate)
            if config.package is not None:
                project, package_hash = config.package.project.name, config.package.hash
                log.info("running package %s of project %s", package_hash, project)
            notify(systemd.READY)
            try:
                yield
            finally:
                notify(systemd.STOPPING)
                if watchdog is not None:
                    watchdog.cancel()
                if events_fd is not None:
                    loop.remove_reader(events_fd)
                expiry.close()
                unsubscribe()
                broadcaster.close()
        # Only reached when closing the HAL raised nothing: every output is in its safe state
        # and released, so there is nothing left for primum-safe to do.
        if not config.simulate:
            declared.remove(config.data_dir)
        app.state.stopped_safely = True
        log.info("stopped outputs=%s", _describe(controller))

    app = FastAPI(title="Primum runtime", version=__version__, lifespan=lifespan)
    app.state.stopped_safely = False
    app.include_router(router)
    # Mounted last: the API's routes are matched first.
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
    install_error_handlers(app)
    return app


def _system_time(config: RuntimeConfig) -> Wall:
    """The time the system tells, once it can be trusted: set from the network since boot,
    or taken as right because the configuration says so."""

    def now() -> datetime | None:
        if config.trust_clock or systemd.clock_synchronized():
            return datetime.now(UTC)
        return None

    return now


def _read_inputs(loop: asyncio.AbstractEventLoop, events_fd: int, controller: Controller) -> None:
    """Read the input changes the descriptor announces. If reading fails the watch ends: the
    descriptor would stay readable and the loop would call again at once, for ever. The
    outputs and the panic button go on working; the inputs keep their last state."""
    try:
        controller.read_inputs()
    except Exception:  # whatever it is, it must not spin the event loop
        loop.remove_reader(events_fd)
        log.exception("reading the inputs failed: inputs are no longer listened to")


def _describe(controller: Controller) -> str:
    return ",".join(
        f"{_named(output.name, output.id)}:{'on' if output.on else 'off'}"
        for output in controller.state().outputs
    )


def _named(name: str, id_: str) -> str:
    """An element in a log: its name, and its id when it has one of its own, since two
    elements of a package may share a name."""
    return name if id_ == name else f"{name} ({id_})"
