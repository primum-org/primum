"""What every driver is: an element of one type, set up from its manifest, on a board.

A driver is made from the element (its name, its wiring, its options), the manifest of its
type (``drivers/<type>.json``) and the limits of its board. It says what it needs of the HAL
(``spec``), and once the HAL has claimed it (``bind``) it is the only way to its element.

An output is commanded with the actions its manifest declares. A command is instant: it
leaves the element in the state the action ends in (its ``endState``, a level from 0 to 100).
Moving an element over time (a ``fade`` with a length) is the engine's, on top of this.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field

from primum_core.generated.model import Driver, DriverAction
from primum_core.values import Value
from primum_runtime.drivers.values import Limits, resolve
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import Hal, InputSpec, OutputSpec, PwmSpec

log = logging.getLogger(__name__)

type Spec = OutputSpec | InputSpec | PwmSpec
# What a board takes for an option of its elements: (element type, option) → (min, max).
type OptionLimits = Mapping[tuple[str, str], tuple[float, float]]

MAX_LEVEL = 100.0


@dataclass(frozen=True)
class ElementConfig:
    """An element as the runtime is told of it: its name, its type, how it is wired and the
    options it gives its driver. Nothing has a default but the options: theirs are the
    manifest's."""

    name: str
    type: str
    pin: int
    active_low: bool
    options: Mapping[str, Value] = field(default_factory=dict[str, Value])


class ElementDriver(ABC):
    """The driver of one element. Its options are resolved when it is made, so a wrong one
    fails before anything is claimed."""

    def __init__(self, element: ElementConfig, manifest: Driver, limits: OptionLimits) -> None:
        self._element = element
        self._manifest = manifest
        board: Limits = {
            option: limit for (kind, option), limit in limits.items() if kind == element.type
        }
        self._options = resolve(element.name, element.options, manifest.config, board)

    @property
    def name(self) -> str:
        return self._element.name

    @property
    def pin(self) -> int:
        return self._element.pin

    @property
    @abstractmethod
    def spec(self) -> Spec:
        """What the element needs of the HAL, every option given."""

    @abstractmethod
    def bind(self, hal: Hal) -> None:
        """Take the element from a HAL that has claimed ``spec``."""


class OutputDriver(ElementDriver):
    """An element that is commanded: it has a level, from 0 (off) to 100 (fully on)."""

    # Whether the hardware did not follow the last command: what was written can no longer be
    # trusted to be the level, until a command is followed again.
    _unsure = False

    @property
    def level(self) -> float:
        """The level the element is at: the last one written, which each command read back.

        After a command the hardware did not follow, the level is read from the hardware
        every time instead, so it is right whatever happened since: the safe state was
        applied, or the hardware recovered on its own. Once the HAL is closed there is
        nothing to read, and it left every output in its safe state: what it wrote stands.
        If the reading itself fails, what was written stands too, and the failure is logged:
        saying the state must never fail, least of all while panic reports its own.
        """
        if not self._unsure:
            return self._written()
        try:
            return self._read()
        except PrimumError as error:
            if error.code is not ErrorCode.HAL_CLOSED:
                log.warning("the level of %s could not be read: %s", self.name, error)
        except Exception as error:  # whatever the hardware raises: the state is still told
            log.warning("the level of %s could not be read: %s", self.name, error)
        return self._written()

    @property
    def actions(self) -> tuple[str, ...]:
        return tuple(action.name for action in self._manifest.actions)

    def command(self, action: str, arguments: Mapping[str, Value] | None = None) -> None:
        """Carry out ``action`` as an instant command: the element goes to the state the
        action ends in, and is read back to be sure.

        Fails with ``element.action_unknown`` (``available``: the ones it has), with what
        ``resolve`` reports for the arguments, and with ``element.level_not_reached`` when the
        hardware reads back another level than the one written.
        """
        declared = self._action(action)
        values = resolve(self.name, arguments or {}, declared.parameters)
        state = declared.end_state
        level = values[state] if isinstance(state, str) else state
        if isinstance(level, bool | str):  # the manifest check refuses it: a state is a number
            raise TypeError(f"the state of {action!r} is not a level: {level!r}")
        self._write(level)
        read = self._read()
        self._unsure = not self._reached(level, read)
        if self._unsure:
            params = {"element": self.name, "level": level, "read": read}
            raise PrimumError(ErrorCode.ELEMENT_LEVEL_NOT_REACHED, params)

    def _action(self, name: str) -> DriverAction:
        for action in self._manifest.actions:
            if action.name == name:
                return action
        params = {"element": self.name, "action": name, "available": self.actions}
        raise PrimumError(ErrorCode.ELEMENT_ACTION_UNKNOWN, params)

    @abstractmethod
    def _write(self, level: float) -> None: ...

    @abstractmethod
    def _written(self) -> float:
        """The last level written successfully, as the HAL remembers it."""

    @abstractmethod
    def _read(self) -> float:
        """The level the hardware reports."""

    @abstractmethod
    def _reached(self, level: float, read: float) -> bool:
        """Whether the level read back is the one written, as far as the element can tell."""
