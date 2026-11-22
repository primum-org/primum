"""Commands on named elements, with panic above them (decision 0006, layer 1).

The API and, later, the engine reach the elements through a ``Controller``, never through the
HAL. It makes a driver for each element, claims them all at once and keeps them by name. There
are no sequences yet: a command goes straight to the driver of its output, unless panic is
active. Panic puts every output in its safe state and refuses commands until it is released.
Inputs are listened to: ``read_inputs`` takes their changes from the HAL.

A command may be a test (test mode, decision 0006): given a duration, it expires on its own,
and its output goes to rest. The controller keeps the deadlines on a monotonic clock it is
given; whoever owns the event loop calls ``expire`` when the next one is due.

Listeners are told the new ``State`` after every change; they must not block.
"""

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from primum_core.generated.model import Driver
from primum_core.values import Value
from primum_runtime.drivers import (
    DigitalInputDriver,
    ElementConfig,
    OptionLimits,
    OutputDriver,
    create_driver,
)
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import Claim, Hal, InputSpec, OutputSpec, PwmSpec

log = logging.getLogger(__name__)

type Listener = Callable[[State], None]
type Clock = Callable[[], float]  # seconds of a monotonic clock

MS_PER_S = 1000
# How long a test may last: long enough to look at a wire, never long enough to forget it.
MIN_TEST_MS = 1_000
MAX_TEST_MS = 300_000
# How long until an output that could not be sent to rest is tried again.
RETRY_REST_S = 5.0


@dataclass(frozen=True)
class OutputState:
    """An output: its level, from 0 to 100, whether that is on at all, and the actions it
    can be asked for (those of its driver's manifest). ``id`` is what it is commanded by;
    without one of its own it is its name."""

    name: str
    on: bool
    level: float
    actions: tuple[str, ...]
    remaining_ms: int | None = None  # of a test: until it expires and the output rests
    rest_failed: bool = False  # its test expired and it could not be sent to rest (yet)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", self.name)


@dataclass(frozen=True)
class InputState:
    name: str
    active: bool
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", self.name)


@dataclass(frozen=True)
class State:
    """What the controller reports: every output and every input, in configuration order,
    and panic."""

    outputs: tuple[OutputState, ...]
    inputs: tuple[InputState, ...]
    panic: bool


class Controller:
    """Owns the elements claimed from one HAL, through their drivers, and the panic latch."""

    def __init__(
        self,
        hal: Hal,
        elements: Sequence[ElementConfig],
        manifests: Mapping[str, Driver],
        limits: OptionLimits,
        before_claim: Callable[[Claim], None] | None = None,
        clock: Clock = time.monotonic,
    ) -> None:
        """Make the driver of every element and claim them all at once. Outputs start in
        their safe state.

        Fails, before anything is claimed, with what ``create_driver`` reports for an element
        (a type without a driver, an option its manifest or its board does not take); then
        with what the HAL reports for the claim. Two elements of one key (its id, or its
        name when it has none) are a mistake of the caller: ``ValueError``.

        ``before_claim`` is called with what is about to be claimed, and may refuse it by
        raising: it is how the service declares its outputs before they can go on.
        """
        keys = [element.key for element in elements]
        if len(set(keys)) != len(keys):
            raise ValueError(f"two elements have the same id or name: {keys}")
        self._hal = hal
        drivers = [create_driver(element, manifests, limits) for element in elements]
        specs = [driver.spec for driver in drivers]
        claim = Claim(
            outputs=[spec for spec in specs if isinstance(spec, OutputSpec)],
            inputs=[spec for spec in specs if isinstance(spec, InputSpec)],
            pwms=[spec for spec in specs if isinstance(spec, PwmSpec)],
        )
        if before_claim is not None:
            before_claim(claim)
        hal.claim(claim)
        for driver in drivers:
            driver.bind(hal)
        self._outputs = {d.key: d for d in drivers if isinstance(d, OutputDriver)}
        self._inputs = {d.pin: d for d in drivers if isinstance(d, DigitalInputDriver)}
        self._panic = False
        self._listeners: list[Listener] = []
        self._clock = clock
        self._deadlines: dict[str, float] = {}  # when the test of each output expires
        self._rest_failed: set[str] = set()  # expired, could not rest: tried again

    def state(self) -> State:
        # One reading per output: its level may come from the hardware, and change.
        levels = {key: driver.level for key, driver in self._outputs.items()}
        now = self._clock()
        outputs = tuple(
            OutputState(
                driver.name,
                levels[key] > 0,
                levels[key],
                driver.actions,
                self._remaining_ms(key, now),
                key in self._rest_failed,
                key,
            )
            for key, driver in self._outputs.items()
        )
        inputs = tuple(
            InputState(driver.name, driver.active, driver.key) for driver in self._inputs.values()
        )
        return State(outputs, inputs, self._panic)

    def command(
        self,
        name: str,
        action: str,
        arguments: Mapping[str, Value] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Ask output ``name`` (its id, or its name when it has no id) for one of the actions
        of its driver, as an instant command.

        With ``duration_ms`` the command is a test: when that time has passed the output goes
        to rest on its own (``expire``). Without it the output stays as the command leaves
        it. Either way the command replaces a test of that output still under way.

        Fails with ``output.unknown`` (param ``name``), ``panic.active`` while panic is on,
        ``test.duration_out_of_range`` (``duration_ms``, ``min_ms``, ``max_ms``), or what the
        driver reports for the action and its arguments: all of them before anything is
        written, and then nothing changes, a test under way included. Once the output is
        being written, whatever fails (``element.level_not_reached``, or an error of the
        hardware reading it back) the output may have changed: listeners are told, a test
        still expires, and a command without a duration does not end a test under way.
        """
        output = self._outputs.get(name)
        if output is None:
            raise PrimumError(ErrorCode.OUTPUT_UNKNOWN, {"name": name})
        if self._panic:
            raise PrimumError(ErrorCode.PANIC_ACTIVE)
        if duration_ms is not None and not MIN_TEST_MS <= duration_ms <= MAX_TEST_MS:
            params = {"duration_ms": duration_ms, "min_ms": MIN_TEST_MS, "max_ms": MAX_TEST_MS}
            raise PrimumError(ErrorCode.TEST_DURATION_OUT_OF_RANGE, params)
        level = output.level_for(action, arguments)  # refused here, nothing has changed
        try:
            output.go_to(level)
        except Exception:
            # Written or not, nobody knows now: the output may be on. A test must still
            # expire, and a test under way must not be ended by a command that failed.
            if duration_ms is not None:
                self._set_deadline(name, duration_ms)
            self._notify()
            raise
        self._set_deadline(name, duration_ms)
        self._notify()

    def next_expiry_s(self) -> float | None:
        """In how many seconds ``expire`` next has something to do (0 if it already has);
        ``None`` while no test is under way."""
        if not self._deadlines:
            return None
        return max(0.0, min(self._deadlines.values()) - self._clock())

    def expire(self) -> None:
        """Send to rest every output whose test has run out; never blocks.

        An output that fails to rest does not stop the others, whatever it raises (the real
        HAL lets an ``OSError`` of a line through): nobody is waiting for an answer here. It
        is logged (once, and again when it rests), its state says so (``rest_failed``), and
        it is tried again every ``RETRY_REST_S`` until it rests, is commanded, or panic takes
        over. That it failed to rest does not say it is on: the write may have worked and
        the read-back failed. Listeners are
        told once, if any test expired.
        """
        now = self._clock()
        expired = [name for name, deadline in self._deadlines.items() if deadline <= now]
        for name in expired:
            del self._deadlines[name]
            try:
                self._outputs[name].rest()
            except Exception as error:  # the others must still be sent to rest
                # Said once, not at every retry: its state goes on saying it meanwhile.
                if name not in self._rest_failed:
                    log.error(
                        "the test of %s expired and it could not be sent to rest "
                        "(trying again every %g s): %s",
                        self._outputs[name].name,
                        RETRY_REST_S,
                        error,
                    )
                self._rest_failed.add(name)
                self._deadlines[name] = now + RETRY_REST_S
            else:
                if name in self._rest_failed:
                    log.info("%s is at rest after all", self._outputs[name].name)
                self._rest_failed.discard(name)
        if expired:
            self._notify()

    def events_fd(self) -> int | None:
        """What to watch to know when ``read_inputs`` has something to read; ``None`` when
        there are no inputs."""
        return self._hal.events_fd()

    def read_inputs(self) -> None:
        """Take the changes of the inputs since the last call; never blocks. Listeners are
        told once, if any input changed."""
        changed = False
        for event in self._hal.read_events():
            changed |= self._inputs[event.pin].handle(event)
        if changed:
            self._notify()

    def panic(self) -> None:
        """Latch panic and put every output in its safe state.

        Panic is latched before the safe state is tried, so no command gets through even if
        some output fails; that failure is raised (``hal.safe_state_incomplete``,
        ``hal.safe_state_unverified``). Every test ends. What panic could not make safe is
        then tried again every ``RETRY_REST_S``, whatever it was doing, and says so
        (``rest_failed``): a panic that fails must not leave an output on for good that
        would have gone off by itself.
        """
        self._panic = True
        self._deadlines.clear()  # nothing is left to expire: everything rests now
        self._rest_failed.clear()
        try:
            self._hal.apply_safe_state()
        except Exception as error:
            self._retry_rest(self._not_safe(error))
            raise
        finally:
            self._notify()

    def release_panic(self) -> None:
        """Accept commands again. Outputs stay in their safe state until commanded."""
        if not self._panic:
            return
        self._panic = False
        self._notify()

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Call ``listener`` with the new state after every change; returns an unsubscribe."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _not_safe(self, error: Exception) -> list[str]:
        """The outputs a failed safe state names (by the pins in its params); every output
        when it does not say which."""
        pins = error.params.get("pins") if isinstance(error, PrimumError) else None
        if not isinstance(pins, tuple):
            return list(self._outputs)
        return [name for name, driver in self._outputs.items() if driver.pin in pins]

    def _retry_rest(self, names: list[str]) -> None:
        retry_at = self._clock() + RETRY_REST_S
        for name in names:
            self._rest_failed.add(name)
            self._deadlines[name] = retry_at

    def _set_deadline(self, name: str, duration_ms: int | None) -> None:
        self._rest_failed.discard(name)  # commanded again: no longer waiting to rest
        if duration_ms is None:
            self._deadlines.pop(name, None)
        else:
            self._deadlines[name] = self._clock() + duration_ms / MS_PER_S

    def _remaining_ms(self, name: str, now: float) -> int | None:
        deadline = self._deadlines.get(name)
        if deadline is None or name in self._rest_failed:  # its test is over
            return None
        return max(0, round((deadline - now) * MS_PER_S))

    def _notify(self) -> None:
        state = self.state()
        for listener in tuple(self._listeners):
            listener(state)
