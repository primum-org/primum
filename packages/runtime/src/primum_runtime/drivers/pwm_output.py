"""``pwm_output``: an element with a level (a dimmed LED, a fan)."""

from primum_runtime.drivers.base import MAX_LEVEL, OutputDriver
from primum_runtime.hal import Hal, PwmOutput, PwmSpec

NS_PER_S = 1_000_000_000
FREQUENCY = "frequencyHz"


class PwmOutputDriver(OutputDriver):
    """The level is the duty cycle of a hardware PWM channel, at the element's frequency."""

    _output: PwmOutput

    @property
    def spec(self) -> PwmSpec:
        return PwmSpec(pin=self._element.pin, frequency_hz=self._frequency_hz())

    def bind(self, hal: Hal) -> None:
        self._output = hal.pwms[self.pin]

    def _written(self) -> float:
        """The level the controller holds for what was written: in whole nanoseconds of the
        period, so a level under one step is 0, and is reported as 0, not as on."""
        period_ns = NS_PER_S // self._frequency_hz()
        return round(self._output.duty * period_ns) / period_ns * MAX_LEVEL

    def _write(self, level: float) -> None:
        self._output.set(level / MAX_LEVEL)

    def _read(self) -> float:
        return self._output.read() * MAX_LEVEL

    def _reached(self, level: float, read: float) -> bool:
        """Within one step of the level: the controller holds the duty cycle in whole
        nanoseconds of the period, so what is read back is the level written, rounded to a
        step (a third reads back as 0.33333 at 1 kHz)."""
        period_ns = NS_PER_S // self._frequency_hz()
        return abs(read - level) <= MAX_LEVEL / period_ns

    def _frequency_hz(self) -> int:
        frequency = self._options[FREQUENCY]
        if not isinstance(frequency, int):  # the manifest declares it an integer
            raise TypeError(f"{FREQUENCY} is not an integer: {frequency!r}")
        return frequency
