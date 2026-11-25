"""What the service runs, and changing it while it runs (decision 0033).

``Running`` is one package on one HAL: the HAL open, its outputs declared and claimed, the
controller, and what wakes it (the timer, the reader of the inputs, the saver of the
persistent variables). Closing it makes every output safe and lets go of the HAL.

``Deployment`` has the one that runs now, and swaps it: a package is stored, and then
activated, in two steps. Activating closes what runs (everything stops, every output goes to
its safe state) and starts the new package from nothing. If the new one cannot be started,
the one before is started again, and the package stays not activated: the board is never
left running nothing because of a package that would not go.

When the service starts with nothing it can run (no package activated yet, or the active one
no longer reads or no longer fits the board) it starts empty: nothing moves, the API is
there to give it a package, and the state says why.
"""

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from uuid import UUID

from primum_core.generated.model import Package
from primum_core.values import Value
from primum_runtime import declared, stored
from primum_runtime.api.broadcast import StateBroadcaster
from primum_runtime.api.expiry import ExpiryTimer
from primum_runtime.api.saving import VariableSaver
from primum_runtime.config import RuntimeConfig
from primum_runtime.control import Controller, Wall
from primum_runtime.deployed import Deployed, Pointers
from primum_runtime.drivers import ElementConfig, load_manifests
from primum_runtime.errors import ErrorCode, ErrorParam, PrimumError
from primum_runtime.hal import Claim, Hal
from primum_runtime.package import LoadedPackage
from primum_runtime.trace import Kind, Trace

log = logging.getLogger(__name__)

type HalFactory = Callable[[], Hal]
type Opening = tuple[Kind, Mapping[str, ErrorParam]]


@dataclass(frozen=True)
class Parts:
    """What every ``Running`` of one service is made with."""

    config: RuntimeConfig
    open_hal: HalFactory
    wall: Wall
    loop: asyncio.AbstractEventLoop
    broadcaster: StateBroadcaster
    trace: Trace
    origin: float  # the instant the times of the trace count from
    clock: Callable[[], float]


class Running:
    """A package, or the elements the options give, or nothing, running on a HAL of its own."""

    def __init__(
        self,
        parts: Parts,
        elements: tuple[ElementConfig, ...],
        package: Package | None,
        opening: Opening | None = None,
    ) -> None:
        """Open a HAL, claim ``elements`` and start. Fails with what the HAL and the
        controller do; then nothing is left open, claimed or declared."""
        self._parts = parts
        self.package = package
        config, loop = parts.config, parts.loop
        self._declared = False
        self._hal = parts.open_hal()
        project = None if package is None else package.project.id
        kept = {} if project is None else stored.read(config.data_dir, project)
        try:
            self.controller = Controller(
                self._hal,
                elements,
                load_manifests(),
                config.limits,
                # A real service declares what it claims before it claims it, so that
                # primum-safe can make it safe if this process dies. A simulated one has
                # nothing to make safe.
                None if config.simulate else self._declare,
                clock=parts.clock,
                package=package,
                wall=parts.wall,
                kept=kept,
                trace=parts.trace,
                origin=parts.origin,
                opening=opening,
            )
        except Exception:
            # A claim that fails leaves nothing claimed: what was declared for it names
            # outputs nobody holds, and primum-safe would fail on it at every stop.
            if self._declared:
                declared.remove(config.data_dir)
            self._hal.close()
            raise
        controller = self.controller
        self._unsubscribe = controller.subscribe(parts.broadcaster.publish)
        # Tests that expire on their own, and the sequences in their time.
        self._expiry = ExpiryTimer(controller, loop.call_later)
        # The values of persistent variables, kept as they change.
        self._saver: VariableSaver | None = None
        if project is not None and _drops(kept, controller.persistent_values()):
            # Before anything replaces it: going back must be able to find them.
            stored.set_aside(config.data_dir, project)
        if project is not None and controller.persistent_values():
            self._saver = VariableSaver(
                controller,
                partial(stored.write, config.data_dir, project),
                loop.call_later,
                partial(_off_the_loop, loop),
                {v: kept[v] for v in controller.persistent_values() if v in kept},
            )
        # Input changes are read when the HAL says there are some: no thread, no polling.
        self._events_fd = controller.events_fd()
        if self._events_fd is not None:
            loop.add_reader(self._events_fd, _read_inputs, loop, self._events_fd, controller)

    def close(self) -> None:
        """Stop: what wakes the controller goes, what is pending of the variables is
        written, and the HAL is closed, which puts every output in its safe state and lets
        go of it. Raises what closing the HAL does: then the outputs are not known to be
        safe, and what was declared stays for ``primum-safe``."""
        if self._events_fd is not None:
            self._parts.loop.remove_reader(self._events_fd)
        self._expiry.close()
        if self._saver is not None:
            self._saver.close()
        self._unsubscribe()
        self._hal.close()
        # Only reached when closing the HAL raised nothing: every output is in its safe
        # state and released, so there is nothing left for primum-safe to do.
        if self._declared:
            declared.remove(self._parts.config.data_dir)

    def _declare(self, claim: Claim) -> None:
        config = self._parts.config
        declared.write(config.data_dir, declared.Declaration.of(config.board.model, claim))
        self._declared = True


class Deployment:
    """What the service runs now, and the packages it could run instead."""

    def __init__(self, parts: Parts) -> None:
        self._parts = parts
        config = parts.config
        # A service told what to drive by its options (a package file, pins) runs that and
        # nothing else: packages are stored and activated only where neither was given.
        self._deployed = (
            Deployed(config.data_dir, load_manifests(), config.board.model)
            if config.deployed
            else None
        )
        self.problem: PrimumError | None = None  # why the active package is not running
        # One change of the packages at a time: a store and an activation wait for a
        # check off the event loop, and another must not come in between.
        self._changing = asyncio.Lock()
        self.running = self._start()

    @property
    def controller(self) -> Controller:
        return self.running.controller

    @property
    def fixed(self) -> bool:
        """Whether the service was told what to drive by its options: then it takes no
        packages."""
        return self._deployed is None

    def pointers(self) -> Pointers:
        return Pointers() if self._deployed is None else self._deployed.pointers()

    def project_of(self, package: str) -> str | None:
        """The name of the project of a package that is kept, as it was when it was
        stored: told without reading the package."""
        return self.pointers().projects.get(package)

    def stop(self) -> None:
        self.running.close()

    async def store(self, content: bytes) -> LoadedPackage:
        """Check a package and keep it, to be activated later. Nothing that runs changes.
        ``package.fixed`` on a service that was told what to drive; what
        ``Deployed.check`` and ``Deployed.keep`` report for a package it does not take.

        The check and the write are off the event loop: a large package takes a second to
        check, and panic must not wait behind it."""
        store = self._store()
        async with self._changing:
            loaded = await asyncio.to_thread(store.check, content)
            await asyncio.to_thread(store.keep, loaded, content)
        told = {"project": loaded.package.project.name, "package": loaded.package.hash}
        self.controller.note(Kind.PACKAGE_STORED, told)
        return loaded

    async def activate(self, package: str) -> None:
        """Run a package that is kept (the staged one, or the previous one) instead of what
        runs now: everything stops, every output goes to its safe state, and the package
        starts from nothing.

        Refused, changing nothing, with ``package.fixed``, ``panic.active`` (panic is
        released by a person, not by a package), ``package.not_stored`` (``hash``), what
        loading it reports, or ``package.unwritable`` when the board cannot write that it
        is the active one: that is written first, before anything that runs is touched.
        If it cannot be started (``package.activation_failed``: ``hash``, ``problem``),
        or what runs cannot be stopped (``package.stop_failed``, the same), what ran
        before is started again and stays the active one.
        """
        store = self._store()
        async with self._changing:
            self._not_in_panic(package)
            before = store.pointers()
            if package == before.active and self.problem is None:
                return  # it runs already
            # Read and checked again, off the event loop: it takes as long as storing it.
            loaded = await asyncio.to_thread(store.load, package)
            self._not_in_panic(package)  # it may have come while the package was being read
            await asyncio.to_thread(store.activate, package)
            try:
                self._swap(loaded, before)
            except PrimumError:
                await asyncio.to_thread(_put_back, store, before)
                raise
            await asyncio.to_thread(store.settle)

    async def rollback(self) -> None:
        """Activate the previous package. ``package.no_previous`` when there is none; the
        rest as ``activate``."""
        previous = self._store().pointers().previous
        if previous is None:
            raise PrimumError(ErrorCode.PACKAGE_NO_PREVIOUS)
        await self.activate(previous)

    def _not_in_panic(self, package: str) -> None:
        """Panic is released by a person, not by a package: the one asked for is refused,
        and the trace says so."""
        if not self.controller.state().panic:
            return
        error = PrimumError(ErrorCode.PANIC_ACTIVE)
        self.controller.note(Kind.PACKAGE_REFUSED, {"hash": package, "problem": error.code.value})
        raise error

    def _swap(self, loaded: LoadedPackage, before: Pointers) -> None:
        """Close what runs and start ``loaded`` in its place, all at once on the event
        loop: nothing is awaited from the look at panic to the package running, so panic
        cannot come in between and be taken away by a controller born without it.

        ``package.stop_failed`` if what runs does not stop, ``package.activation_failed``
        if the package does not start: then what ran before runs again, and whoever
        listens to the state is told, since everything stopped on the way."""
        package = loaded.package.hash
        self._not_in_panic(package)  # it may have come while the board wrote its state
        told: dict[str, ErrorParam] = {
            "project": loaded.package.project.name,
            "package": package,
        }
        if before.active is not None and before.active != package:
            told["previous"] = before.active
        if package == before.previous:
            told["rollback"] = True
        was = self.running
        try:
            # Its sequences end here, and the trace says so before the package that
            # replaces them.
            was.controller.stop_all("package")
            was.close()
        except Exception as error:
            # Not the package's doing, and the outputs are not known to be safe: what ran
            # is claimed again, which puts them in their safe state.
            log.exception("what runs could not be stopped to activate package %s", package)
            self._refused(was, before, package, ErrorCode.PACKAGE_STOP_FAILED.value)
            raise PrimumError(ErrorCode.PACKAGE_STOP_FAILED, _told(package, error)) from error
        try:
            self.running = self._run(loaded, (Kind.PACKAGE_ACTIVATED, told))
        except Exception as error:
            log.exception("package %s could not be activated: what ran before runs again", package)
            params = _told(package, error)
            problem = params.get("problem")
            self._refused(was, before, package, problem if isinstance(problem, str) else None)
            raise PrimumError(ErrorCode.PACKAGE_ACTIVATION_FAILED, params) from error
        self.problem = None
        log.info("package %s of project %s activated", package, loaded.package.project.name)
        self._parts.broadcaster.publish(self.controller.state())

    def _refused(self, was: Running, before: Pointers, package: str, problem: str | None) -> None:
        """Start again what ran before a package that did not go, and tell whoever listens
        to the state: it shows what was running, and everything stopped."""
        params: dict[str, ErrorParam] = {"hash": package}
        if problem is not None:
            params["problem"] = problem
        self.running = self._again(was, before, (Kind.PACKAGE_REFUSED, params))
        self._parts.broadcaster.publish(self.controller.state())

    def _store(self) -> Deployed:
        if self._deployed is None:
            raise PrimumError(ErrorCode.PACKAGE_FIXED)
        return self._deployed

    def _start(self) -> Running:
        """What the service starts with: what its options say, or the active package, or
        nothing when there is none it can run (and then ``problem`` says why).

        Whatever keeps the active package from running, the service starts: one that no
        longer reads, one that no longer fits the board, one whose elements cannot be
        claimed (a line another program holds). A service that died of it would be
        restarted by systemd for ever, and could not be given another package."""
        config = self._parts.config
        if self._deployed is None:
            return Running(self._parts, config.elements, config.package)
        active = self._deployed.pointers().active
        if active is None:
            return Running(self._parts, (), None)
        try:
            loaded = self._deployed.load(active)
            running = self._run(loaded, None)
        except Exception as error:
            log.exception("the active package (%s) cannot be run: the service starts empty", active)
            self.problem = _problem(error, active)
            return Running(self._parts, (), None)
        log.info("running package %s of project %s", active, loaded.package.project.name)
        return running

    def _run(self, loaded: LoadedPackage, opening: Opening | None) -> Running:
        return Running(self._parts, loaded.elements, loaded.package, opening)

    def _again(self, was: Running, before: Pointers, opening: Opening) -> Running:
        """Start again what ran before a package that would not go; nothing at all, if that
        does not start either."""
        if was.package is not None and self._deployed is not None and before.active is not None:
            try:
                return self._run(self._deployed.load(before.active), opening)
            except Exception:
                log.exception("what ran before does not start either: the service runs nothing")
        return Running(self._parts, (), None, opening)


def _problem(error: Exception, package: str) -> PrimumError:
    """Why a package is not running, as an error is told: the error itself when it has a
    code, and else that it could not be started."""
    if isinstance(error, PrimumError):
        return error
    return PrimumError(ErrorCode.PACKAGE_ACTIVATION_FAILED, {"hash": package})


def _told(package: str, error: Exception) -> dict[str, ErrorParam]:
    """The params of an activation that failed: the package, and the code of what kept it
    from going when it has one."""
    params: dict[str, ErrorParam] = {"hash": package}
    if isinstance(error, PrimumError):
        params["problem"] = error.code.value
    return params


def _put_back(store: Deployed, before: Pointers) -> None:
    """The pointers as they were before an activation that did not go. If even that cannot
    be written it is logged: what runs is what ran before, and the state on the card will
    say otherwise until the next activation."""
    try:
        store.restore(before)
    except PrimumError:
        log.exception("the packages' state could not be put back as it was")


def _drops(kept: Mapping[UUID, Value], now: Mapping[UUID, Value]) -> bool:
    """Whether writing ``now`` over what is kept for the project would lose something of
    it: a value that was kept and is not what its variable starts at (the variable is gone,
    or no longer takes it), or a file whose values could not be used at all (unreadable;
    nothing kept sets nothing aside)."""
    return not kept or any(now.get(variable) != value for variable, value in kept.items())


def _off_the_loop(
    loop: asyncio.AbstractEventLoop,
    work: Callable[[], None],
    done: Callable[[BaseException | None], None],
) -> None:
    """Run ``work`` in a thread, and call ``done`` on the loop with what it raised, if
    anything: a write to the card must not keep the loop, and panic with it, waiting."""
    future = loop.run_in_executor(None, work)
    # A service that is stopping cancels what waits: its last save is made on the way out.
    future.add_done_callback(
        lambda finished: None if finished.cancelled() else done(finished.exception())
    )


def _read_inputs(loop: asyncio.AbstractEventLoop, events_fd: int, controller: Controller) -> None:
    """Read the input changes the descriptor announces. If reading fails the watch ends: the
    descriptor would stay readable and the loop would call again at once, for ever. The
    outputs and the panic button go on working; the inputs keep their last state."""
    try:
        controller.read_inputs()
    except Exception:  # whatever it is, it must not spin the event loop
        loop.remove_reader(events_fd)
        log.exception("reading the inputs failed: inputs are no longer listened to")
