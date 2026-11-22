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
    # A test: after this long the output goes to rest on its own. Its limits are the
    # controller's, answered with their own code.
    durationMs: int | None = None  # noqa: N815 (the name in the JSON body)


class VariableValue(_Body):
    """The value to give a variable: ``{"value": 40}``. Of its type and within its limits,
    which are the controller's to check, answered with their own codes."""

    value: int | float | bool | str


class OutputStateBody(_Body):
    id: str  # what the output is commanded by: PUT /api/outputs/{id}
    name: str
    on: bool
    level: float
    actions: list[str]
    remainingMs: int | None  # noqa: N815 (the name in the JSON body)
    restFailed: bool  # noqa: N815
    # Who commands it: "manual", "test", "sequence", or nobody (it rests).
    controlledBy: str | None  # noqa: N815


class InputStateBody(_Body):
    id: str
    name: str
    active: bool


class SequenceStateBody(_Body):
    id: str  # what it is started and stopped by: POST /api/sequences/{id}/start
    name: str
    running: bool


class VariableStateBody(_Body):
    id: str  # what it is set by: PUT /api/variables/{id}
    name: str
    type: str
    value: int | float | bool | str
    min: float | None
    max: float | None
    setting: bool


class StateBody(_Body):
    outputs: list[OutputStateBody]
    inputs: list[InputStateBody]
    panic: bool
    sequences: list[SequenceStateBody]  # of the package that is running; none without one
    variables: list[VariableStateBody]  # of that package too, with the value each has now

    @classmethod
    def of(cls, state: State) -> "StateBody":
        outputs = [
            OutputStateBody(
                id=output.id,
                name=output.name,
                on=output.on,
                level=output.level,
                actions=list(output.actions),
                remainingMs=output.remaining_ms,
                restFailed=output.rest_failed,
                controlledBy=output.controlled_by,
            )
            for output in state.outputs
        ]
        inputs = [
            InputStateBody(id=item.id, name=item.name, active=item.active) for item in state.inputs
        ]
        sequences = [
            SequenceStateBody(id=item.id, name=item.name, running=item.running)
            for item in state.sequences
        ]
        variables = [
            VariableStateBody(
                id=item.id,
                name=item.name,
                type=item.type,
                value=item.value,
                min=item.min,
                max=item.max,
                setting=item.setting,
            )
            for item in state.variables
        ]
        return cls(
            outputs=outputs,
            inputs=inputs,
            panic=state.panic,
            sequences=sequences,
            variables=variables,
        )


class ErrorBody(_Body):
    """Every error response: a code and its params, never text (decision 0009)."""

    code: str
    params: dict[str, ErrorParam]
