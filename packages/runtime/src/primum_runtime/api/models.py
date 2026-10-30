"""Request and response bodies of the HTTP API (pydantic at this edge only, decision 0008)."""

from pydantic import BaseModel, ConfigDict

from primum_runtime.control import State
from primum_runtime.errors import ErrorParam


class _Body(BaseModel):
    # Strict: "yes" or 1 are not booleans, and unknown fields are mistakes, not extensions.
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class OutputCommand(_Body):
    on: bool


class OutputStateBody(_Body):
    name: str
    on: bool


class StateBody(_Body):
    outputs: list[OutputStateBody]
    panic: bool

    @classmethod
    def of(cls, state: State) -> "StateBody":
        outputs = [OutputStateBody(name=output.name, on=output.on) for output in state.outputs]
        return cls(outputs=outputs, panic=state.panic)


class ErrorBody(_Body):
    """Every error response: a code and its params, never text (decision 0009)."""

    code: str
    params: dict[str, ErrorParam]
