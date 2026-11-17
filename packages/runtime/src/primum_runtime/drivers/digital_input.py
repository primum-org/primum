"""``digital_input``: an element that is listened to (a button, a sensor)."""

import logging

from primum_runtime.drivers.base import ElementDriver
from primum_runtime.hal import DigitalInput, Hal, InputEvent, InputSpec, Pull

log = logging.getLogger(__name__)

PULL = "pull"
DEBOUNCE = "debounceMs"


class DigitalInputDriver(ElementDriver):
    """Its state follows the events of its line.

    The state is taken from each event, never assumed to alternate: a pulse too short for the
    kernel to tell its edges apart gives two events that say the same. A jump in the events'
    sequence numbers says some were lost (the kernel drops the oldest of a burst it cannot
    hold): the state is still right, since the last event carries it, but a count of presses
    is not, so the loss is counted and logged.
    """

    _input: DigitalInput
    _active = False
    _sequence = 0  # of the last event seen
    _lost = 0

    @property
    def spec(self) -> InputSpec:
        debounce = self._options[DEBOUNCE]
        if not isinstance(debounce, int):  # the manifest declares it an integer
            raise TypeError(f"{DEBOUNCE} is not an integer: {debounce!r}")
        return InputSpec(
            pin=self._element.pin,
            pull=Pull(self._options[PULL]),
            active_low=self._element.active_low,
            debounce_ms=debounce,
        )

    def bind(self, hal: Hal) -> None:
        self._input = hal.inputs[self.pin]
        self._active = self._input.read()

    @property
    def active(self) -> bool:
        """The state the last event left, or the one read when the input was claimed."""
        return self._active

    @property
    def lost_events(self) -> int:
        """How many events never arrived, by the gaps in their sequence numbers."""
        return self._lost

    def handle(self, event: InputEvent) -> bool:
        """Take the state from an event of this input; whether the state changed."""
        missing = event.sequence - self._sequence - 1
        if missing > 0:
            self._lost += missing
            log.warning("input %s lost %d events (%d in all)", self.name, missing, self._lost)
        self._sequence = event.sequence
        changed = event.active != self._active
        self._active = event.active
        return changed
