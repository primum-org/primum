"""``digital_output``: an element that is on or off (an LED, a relay)."""

from primum_runtime.drivers.base import MAX_LEVEL, OutputDriver
from primum_runtime.hal import DigitalOutput, Hal, OutputSpec


class DigitalOutputDriver(OutputDriver):
    """On is the level 100 and off the level 0; any level above 0 turns it on. Which
    electrical level is "on" is the element's ``active_low``."""

    _output: DigitalOutput

    @property
    def spec(self) -> OutputSpec:
        return OutputSpec(pin=self._element.pin, active_low=self._element.active_low)

    def bind(self, hal: Hal) -> None:
        self._output = hal.outputs[self.pin]

    def _written(self) -> float:
        return MAX_LEVEL if self._output.is_on else 0.0

    def _write(self, level: float) -> None:
        self._output.set(level > 0)

    def _read(self) -> float:
        return MAX_LEVEL if self._output.read() else 0.0

    def _reached(self, level: float, read: float) -> bool:
        return (read > 0) == (level > 0)
