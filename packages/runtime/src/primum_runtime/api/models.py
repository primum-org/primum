"""Request and response bodies of the HTTP API (pydantic at this edge only, decision 0008)."""

from pydantic import BaseModel, ConfigDict, Field

from primum_runtime.control import State
from primum_runtime.errors import ErrorParam


class _Body(BaseModel):
    # Strict: "yes" or 1 are not booleans, and unknown fields are mistakes, not extensions.
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class OutputCommand(_Body):
    """One of the actions of the output's driver, with the arguments it takes by name:
    ``{"action": "on"}``, ``{"action": "set", "arguments": {"level": 40}}``."""

    action: str
    arguments: dict[str, int | float | bool | str] = Field(default_factory=dict)


class OutputStateBody(_Body):
    name: str
    on: bool
    level: float
    actions: list[str]


class InputStateBody(_Body):
    name: str
    active: bool


class StateBody(_Body):
    outputs: list[OutputStateBody]
    inputs: list[InputStateBody]
    panic: bool

    @classmethod
    def of(cls, state: State) -> "StateBody":
        outputs = [
            OutputStateBody(
                name=output.name, on=output.on, level=output.level, actions=list(output.actions)
            )
            for output in state.outputs
        ]
        inputs = [InputStateBody(name=item.name, active=item.active) for item in state.inputs]
        return cls(outputs=outputs, inputs=inputs, panic=state.panic)


class ErrorBody(_Body):
    """Every error response: a code and its params, never text (decision 0009)."""

    code: str
    params: dict[str, ErrorParam]
