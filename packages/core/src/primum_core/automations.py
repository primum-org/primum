"""What the automations of a package do when something happens (decision 0029).

Pure: given what happened (an event, by its id) and the values the variables have, it says
which automations act, and what an increment leaves a variable at. Whoever runs the package
does the rest: starts and stops the sequences, keeps the values.

- An automation acts when it is enabled, the event (or the schedule) is one of its ``when``,
  every schedule of its ``during`` has a window open, and its condition holds
  (``primum_core.expressions``). Without a condition it always holds.
- **Every condition is worked out on the same values**: those the variables had when the
  event came, before any automation acted. Which automations act never depends on the order
  they are in. Their actions then run in the order of the package, each automation's in the
  order it lists them.
- A condition that cannot be worked out (``expressions.Failure``) does not hold; it is
  reported, with why, for whoever runs the package to tell.
"""

import math
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from primum_core.expressions import MAX_EXACT, Failure, evaluate
from primum_core.generated.model import PackageAutomation, PackageVariable
from primum_core.values import Value

DEFAULT_INCREMENT = 1
TIME_UNKNOWN = "time_unknown"  # why an automation that waits for a window could not be judged
# Where a variable without a limit stops: the largest number a double holds, and for a
# whole number the largest a condition can read (``expressions.MAX_EXACT`` is out).
LARGEST = 1.7976931348623157e308
LARGEST_WHOLE = MAX_EXACT - 1


@dataclass(frozen=True)
class Verdict:
    """An automation an event concerns, and whether it ``acts``: its condition held. When
    it does not, ``failure`` says why the condition could not be worked out, if that is
    why; without one the condition was simply false."""

    automation: PackageAutomation
    acts: bool
    failure: Failure | None = None


def verdicts(
    automations: Iterable[PackageAutomation],
    source: UUID,
    values: Mapping[UUID, Value],
    open_schedules: Collection[UUID] | None = (),
) -> tuple[Verdict, ...]:
    """What each automation that ``source`` concerns does, in the order given: every one
    that is enabled and waits for it, whether its condition holds, is false or failed. One
    that is disabled or does not wait for ``source`` is left out.

    ``open_schedules`` are the schedules with a window open now, by id: an automation that
    names some (``during``) acts only while all of them are. ``None`` says the time is not
    known: such an automation then does not act, and that is a failure (``time_unknown``),
    since nobody can say whether it should have."""
    found: list[Verdict] = []
    for automation in automations:
        if not automation.enabled or source not in automation.when:
            continue
        if automation.during and open_schedules is None:
            found.append(Verdict(automation, acts=False, failure=Failure(TIME_UNKNOWN)))
            continue
        if not all(schedule in (open_schedules or ()) for schedule in automation.during):
            found.append(Verdict(automation, acts=False))
            continue
        holds = evaluate(automation.if_, values) if automation.if_ else True
        if isinstance(holds, Failure):
            found.append(Verdict(automation, acts=False, failure=holds))
        else:
            found.append(Verdict(automation, acts=holds is True))
    return tuple(found)


def incremented(variable: PackageVariable, value: Value, by: float | None) -> Value:
    """What ``increment_variable`` leaves a numeric variable at: ``value`` plus ``by`` (1 when
    absent), held to the limits the variable has. One that would pass a limit stays at it.

    The result is of the variable's type: a whole number stays whole at its limit, though a
    package writes limits as numbers with decimals. Without a limit on a side, a whole
    number stops at the largest a condition can read (below 2^53) and a number with
    decimals at the largest there is."""
    if isinstance(value, bool | str):  # a package that holds together never increments one
        raise TypeError(f"{variable.name} is not a number: {value!r}")
    amount = DEFAULT_INCREMENT if by is None else by
    if variable.type == "integer":
        low = -LARGEST_WHOLE if variable.min is None else math.ceil(variable.min)
        high = LARGEST_WHOLE if variable.max is None else math.floor(variable.max)
        return min(max(int(value) + int(amount), low), high)
    try:
        result = value + amount
    except OverflowError:  # a whole number no double holds, plus one with decimals
        result = LARGEST if amount > 0 else -LARGEST
    low = -LARGEST if variable.min is None else variable.min
    high = LARGEST if variable.max is None else variable.max
    return min(max(result, low), high)
