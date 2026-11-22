"""Request and response bodies of the HTTP API (pydantic at this edge only, decision 0008)."""

from pydantic import BaseModel, ConfigDict, Field

from primum_runtime.control import State
from primum_runtime.errors import ErrorParam
from primum_runtime.trace import Entry, Trace


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
    lostEvents: int  # noqa: N815 (changes that never arrived, and so started nothing)


class EventStateBody(_Body):
    id: str  # what it is fired by, unless its source is an element: POST /api/events/{id}/fire
    name: str
    source: str  # "element", "ui" or "api"


class ScheduleStateBody(_Body):
    id: str
    name: str
    open: bool | None  # whether one of its windows is open now; null while the time is not known


class AutomationStateBody(_Body):
    id: str
    name: str
    enabled: bool
    # What went wrong the last time something it waits for happened, as an error is told.
    problem: "ErrorBody | None"


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
    persistent: bool  # kept across a restart


class StateBody(_Body):
    outputs: list[OutputStateBody]
    inputs: list[InputStateBody]
    panic: bool
    sequences: list[SequenceStateBody]  # of the package that is running; none without one
    variables: list[VariableStateBody]  # of that package too, with the value each has now
    events: list[EventStateBody]
    automations: list[AutomationStateBody]
    schedules: list[ScheduleStateBody]
    timeKnown: bool  # noqa: N815 (until the board knows the time, no schedule happens)
    # The values of persistent variables could not be kept: a restart would lose changes.
    variablesUnsaved: bool  # noqa: N815

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
            InputStateBody(
                id=item.id, name=item.name, active=item.active, lostEvents=item.lost_events
            )
            for item in state.inputs
        ]
        events = [
            EventStateBody(id=item.id, name=item.name, source=item.source) for item in state.events
        ]
        automations = [
            AutomationStateBody(
                id=item.id,
                name=item.name,
                enabled=item.enabled,
                problem=None
                if item.problem is None
                else ErrorBody(code=item.problem.code.value, params=dict(item.problem.params)),
            )
            for item in state.automations
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
                persistent=item.persistent,
            )
            for item in state.variables
        ]
        return cls(
            outputs=outputs,
            inputs=inputs,
            panic=state.panic,
            sequences=sequences,
            variables=variables,
            events=events,
            automations=automations,
            schedules=[
                ScheduleStateBody(id=item.id, name=item.name, open=item.open)
                for item in state.schedules
            ],
            timeKnown=state.time_known,
            variablesUnsaved=state.variables_unsaved,
        )


class TraceEntryBody(_Body):
    """One thing the board did: a ``kind`` and its ``params``, as an error is a code and
    its params. ``cause`` is the number of the entry that led to it, if one did."""

    number: int
    atMs: int  # noqa: N815 (since the service started, on the clock that never jumps)
    time: str | None  # the time of day (ISO 8601, UTC), when the board knows it
    kind: str
    params: dict[str, ErrorParam]
    cause: int | None

    @classmethod
    def of(cls, entry: Entry) -> "TraceEntryBody":
        return cls(
            number=entry.number,
            atMs=entry.at_ms,
            time=None if entry.time is None else entry.time.isoformat(),
            kind=entry.kind,
            params=dict(entry.params),
            cause=entry.cause,
        )


class TraceBody(_Body):
    """The entries asked for, oldest first. ``first`` is the oldest entry still kept and
    ``last`` the newest ever noted: asked for entries after one that is below ``first`` less
    one, some were noted and are gone."""

    entries: list[TraceEntryBody]
    first: int
    last: int

    @classmethod
    def of(cls, trace: Trace, after: int) -> "TraceBody":
        entries = [TraceEntryBody.of(entry) for entry in trace.entries(after)]
        return cls(entries=entries, first=trace.first, last=trace.last)


class ErrorBody(_Body):
    """Every error response: a code and its params, never text (decision 0009)."""

    code: str
    params: dict[str, ErrorParam]
