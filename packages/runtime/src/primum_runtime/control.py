"""Who commands each output: panic, then a person, then the sequences (decision 0006).

The API and the engine reach the elements through a ``Controller``, never through the HAL. It
makes a driver for each element, claims them all at once and keeps them by key (an element's
id, or its name when it has none). It is the arbiter of every output it owns. From the top:

1. **Panic**: every output in its safe state, every sequence stopped, and nothing else
   accepted until it is released.
2. **A person**: a command of the API. Without a duration it is manual control and stays
   until it is released; with one it is a test, and expires on its own. One or the other per
   output: a command replaces the one before.
3. **The sequences** of the package that is running, as the engine says (``engine``): the
   highest priority, then the command that started last.

When a layer has nothing to say, the one below does; when none has, the output rests in its
driver's safe state. So a test that expires, or manual control that is released, gives the
output back to the sequences, not to rest.

An output is only written when what it should be at changes. One that cannot be taken there
does not stop the others, whatever it raises: it is logged once, its state says so
(``rest_failed``), and it is tried again every ``RETRY_REST_S`` until it gets there.

Time is a monotonic clock the controller is given. Whoever owns the event loop calls
``expire`` when ``next_expiry_s`` says: a test runs out, a command of a sequence starts or
ends, or an output is due to be tried again. Inputs are listened to: ``read_inputs`` takes
their changes from the HAL. Listeners are told the new ``State`` after every change; they
must not block.
"""

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from primum_core.generated.model import Command, Driver, Package
from primum_core.values import Value
from primum_runtime.drivers import (
    DigitalInputDriver,
    ElementConfig,
    OptionLimits,
    OutputDriver,
    create_driver,
)
from primum_runtime.engine import Engine
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import Claim, Hal, InputSpec, OutputSpec, PwmSpec

log = logging.getLogger(__name__)

type Listener = Callable[[State], None]
type Clock = Callable[[], float]  # seconds of a monotonic clock

MS_PER_S = 1000
# How long a test may last: long enough to look at a wire, never long enough to forget it.
MIN_TEST_MS = 1_000
MAX_TEST_MS = 300_000
# How long until an output that could not be taken where it should be is tried again.
RETRY_REST_S = 5.0
# Who commands an output, as its state says it.
MANUAL, TEST, SEQUENCE = "manual", "test", "sequence"


@dataclass(frozen=True)
class OutputState:
    """An output: its level, from 0 to 100, whether that is on at all, and the actions it
    can be asked for (those of its driver's manifest). ``id`` is what it is commanded by;
    without one of its own it is its name. ``controlled_by`` says who commands it: a person
    (``manual``, or ``test`` with its time left), a ``sequence``, or nobody: it rests."""

    name: str
    on: bool
    level: float
    actions: tuple[str, ...]
    remaining_ms: int | None = None  # of a test: until it expires
    rest_failed: bool = False  # it could not be taken where it should be (yet)
    id: str = ""
    controlled_by: str | None = None

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
class SequenceState:
    """A sequence of the package that is running, and whether it is running."""

    id: str
    name: str
    running: bool


@dataclass(frozen=True)
class State:
    """What the controller reports: every output and every input, in configuration order,
    panic, and the sequences of the package, if it runs one."""

    outputs: tuple[OutputState, ...]
    inputs: tuple[InputState, ...]
    panic: bool
    sequences: tuple[SequenceState, ...] = ()


@dataclass(frozen=True)
class _Held:
    """What a person asked of an output: the level, and until when if it is a test."""

    level: float
    until: float | None = None


class Controller:
    """Owns the elements claimed from one HAL, through their drivers: their arbiter."""

    def __init__(
        self,
        hal: Hal,
        elements: Sequence[ElementConfig],
        manifests: Mapping[str, Driver],
        limits: OptionLimits,
        before_claim: Callable[[Claim], None] | None = None,
        clock: Clock = time.monotonic,
        package: Package | None = None,
    ) -> None:
        """Make the driver of every element and claim them all at once. Outputs start in
        their safe state, and no sequence of ``package`` is running.

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
        self._held: dict[str, _Held] = {}  # what a person asked of each output
        self._retry_at: dict[str, float] = {}  # outputs not where they should be: when next
        # The level each output was last taken to, while that is known: the claim left them
        # all in their safe state.
        self._at = {key: output.rest_level for key, output in self._outputs.items()}
        self._engine = None if package is None else Engine(package)
        # A variable is read at its initial value until variables change (block 4.3c).
        variables = () if package is None else package.variables
        self._variables: Mapping[UUID, Value] = {v.id: v.initial for v in variables}
        self._levels: dict[Command, float] = {}  # what each command of a sequence asks
        self._ran: tuple[UUID, ...] = ()  # the sequences running when listeners were last told

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
                key in self._retry_at,
                key,
                self._controlled_by(key, now),
            )
            for key, driver in self._outputs.items()
        )
        inputs = tuple(
            InputState(driver.name, driver.active, driver.key) for driver in self._inputs.values()
        )
        return State(outputs, inputs, self._panic, self._sequences(now))

    def command(
        self,
        name: str,
        action: str,
        arguments: Mapping[str, Value] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Ask output ``name`` (its id, or its name when it has no id) for one of the actions
        of its driver, as an instant command, over whatever the sequences say.

        Without ``duration_ms`` it is manual control: the output stays as the command leaves
        it until it is released (``release``) or commanded again. With it the command is a
        test: when that time has passed the output goes back to what the sequences say, or to
        rest (``expire``). Either way it replaces what was asked of that output before.

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
        until = None if duration_ms is None else self._clock() + duration_ms / MS_PER_S
        try:
            output.go_to(level)
        except Exception:
            # Written or not, nobody knows now: the output may be on. A test must still
            # expire, and a test under way must not be ended by a command that failed.
            if until is not None:
                self._held[name] = _Held(level, until)
            self._at.pop(name, None)
            self._notify()
            raise
        self._held[name] = _Held(level, until)
        self._at[name] = level
        self._retry_at.pop(name, None)  # commanded again: no longer waiting to get anywhere
        self._notify()

    def release(self, name: str) -> None:
        """Let go of output ``name``: what a person asked of it, manual control or a test,
        is over, and it goes to what the sequences say, or to rest. One that nobody holds
        stays as it is. ``output.unknown`` for one there is not."""
        if name not in self._outputs:
            raise PrimumError(ErrorCode.OUTPUT_UNKNOWN, {"name": name})
        if self._held.pop(name, None) is None:
            return
        self._settle(self._clock())
        self._notify()

    def start_sequence(self, sequence: str) -> None:
        """Start a sequence of the package, by its id. ``sequence.unknown`` (``id``) for one
        the package does not have, or with no package; ``panic.active`` while panic is on."""
        engine, found = self._sequence(sequence)
        if self._panic:
            raise PrimumError(ErrorCode.PANIC_ACTIVE)
        now = self._clock()
        engine.start(found, _ms(now))
        log.info("sequence %s started", sequence)
        self._settle(now)
        self._notify()

    def stop_sequence(self, sequence: str) -> None:
        """Stop a sequence of the package, by its id; one that is not running stays so.
        ``sequence.unknown`` for one the package does not have."""
        engine, found = self._sequence(sequence)
        engine.stop(found)
        log.info("sequence %s stopped", sequence)
        self._settle(self._clock())
        self._notify()

    def next_expiry_s(self) -> float | None:
        """In how many seconds ``expire`` next has something to do (0 if it already has): a
        test runs out, a command of a running sequence starts or ends, or an output is due
        to be tried again. ``None`` while nothing is pending."""
        now = self._clock()
        due = [held.until for held in self._held.values() if held.until is not None]
        due += self._retry_at.values()
        if self._engine is not None:
            change = self._engine.next_change_ms(_ms(now))
            if change is not None:
                due.append(change / MS_PER_S)
        return max(0.0, min(due) - now) if due else None

    def expire(self) -> None:
        """Bring every output to what it should be at now; never blocks.

        Tests that have run out are over, the sequences are where their time says, and an
        output that could not be taken where it should be is tried again if it is due. An
        output that fails does not stop the others, whatever it raises (the real HAL lets an
        ``OSError`` of a line through): nobody is waiting for an answer here. That it failed
        does not say it is on: the write may have worked and the read-back failed. Listeners
        are told once, if anything changed.
        """
        now = self._clock()
        expired = [key for key, held in self._held.items() if _over(held, now)]
        for key in expired:
            del self._held[key]
        changed = self._settle(now)
        if expired or changed or self._running(now) != self._ran:
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
        """Latch panic, stop every sequence and put every output in its safe state.

        Panic is latched before the safe state is tried, so no command gets through even if
        some output fails; that failure is raised (``hal.safe_state_incomplete``,
        ``hal.safe_state_unverified``). Every test and all manual control end. What panic
        could not make safe is then tried again every ``RETRY_REST_S``, whatever it was
        doing, and says so (``rest_failed``): a panic that fails must not leave an output on
        for good that would have gone off by itself.
        """
        self._panic = True
        self._held.clear()  # nothing is left to expire: everything rests now
        self._retry_at.clear()
        if self._engine is not None:
            self._engine.stop_all()
        not_safe: list[str] = []
        try:
            self._hal.apply_safe_state()
        except Exception as error:
            not_safe = self._not_safe(error)
            raise
        finally:
            retry_at = self._clock() + RETRY_REST_S
            for key, output in self._outputs.items():
                if key in not_safe:
                    self._retry_at[key] = retry_at
                    self._at.pop(key, None)
                else:
                    self._at[key] = output.rest_level
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

    def _wanted(self, key: str, now: float) -> float:
        """The level output ``key`` should be at: what the highest layer with something to
        say asks of it."""
        output = self._outputs[key]
        if self._panic:
            return output.rest_level
        held = self._held.get(key)
        if held is not None:
            return held.level
        command = self._asked(key, now)
        return output.rest_level if command is None else self._level_of(command, output)

    def _asked(self, key: str, now: float) -> Command | None:
        """What the sequences ask of output ``key``, if anything."""
        if self._engine is None:
            return None
        asked = self._engine.asked(UUID(key), _ms(now))
        return None if asked is None else asked.command

    def _level_of(self, command: Command, output: OutputDriver) -> float:
        level = self._levels.get(command)
        if level is None:
            arguments = {
                argument.name: self._variables[argument.variable]
                if argument.variable is not None
                else argument.value
                for argument in command.arguments
            }
            given = {name: value for name, value in arguments.items() if value is not None}
            level = self._levels[command] = output.level_for(command.action, given)
        return level

    def _settle(self, now: float) -> bool:
        """Take each output to the level it should be at, if it is not known to be there, or
        if it failed to get there and is due to be tried again. Whether anything was done."""
        changed = False
        for key, output in self._outputs.items():
            retry_at = self._retry_at.get(key)
            if retry_at is None and key in self._at and self._at[key] == self._wanted(key, now):
                continue
            if retry_at is not None and retry_at > now:
                continue
            changed = True
            try:
                wanted = self._wanted(key, now)
                output.go_to(wanted)
            except Exception as error:  # the others must still be taken where they should be
                # Said once, not at every retry: its state goes on saying it meanwhile.
                if retry_at is None:
                    log.error(
                        "%s could not be taken where it should be (trying again every %g s): %s",
                        output.name,
                        RETRY_REST_S,
                        error,
                    )
                self._retry_at[key] = now + RETRY_REST_S
                self._at.pop(key, None)
            else:
                if retry_at is not None:
                    log.info("%s is where it should be after all", output.name)
                    del self._retry_at[key]
                self._at[key] = wanted
        return changed

    def _controlled_by(self, key: str, now: float) -> str | None:
        if self._panic:
            return None
        held = self._held.get(key)
        if held is not None:
            return MANUAL if held.until is None else TEST
        return None if self._asked(key, now) is None else SEQUENCE

    def _sequence(self, sequence: str) -> tuple[Engine, UUID]:
        """The engine and the id of a sequence asked for by text; ``sequence.unknown`` when
        there is no package, or the text is no id."""
        try:
            found = UUID(sequence)
        except ValueError:
            found = None
        if self._engine is None or found is None:
            raise PrimumError(ErrorCode.SEQUENCE_UNKNOWN, {"id": sequence})
        return self._engine, found

    def _running(self, now: float) -> tuple[UUID, ...]:
        if self._engine is None:
            return ()
        return tuple(run.sequence for run in self._engine.running(_ms(now)))

    def _sequences(self, now: float) -> tuple[SequenceState, ...]:
        if self._engine is None:
            return ()
        running = set(self._running(now))
        return tuple(
            SequenceState(str(sequence.id), sequence.name, sequence.id in running)
            for sequence in self._engine.sequences
        )

    def _remaining_ms(self, key: str, now: float) -> int | None:
        held = self._held.get(key)
        if held is None or held.until is None:
            return None
        return max(0, round((held.until - now) * MS_PER_S))

    def _notify(self) -> None:
        self._ran = self._running(self._clock())
        state = self.state()
        for listener in tuple(self._listeners):
            listener(state)


def _ms(seconds: float) -> int:
    """A time of the controller's clock in the whole milliseconds the engine counts in."""
    return round(seconds * MS_PER_S)


def _over(held: _Held, now: float) -> bool:
    return held.until is not None and held.until <= now
