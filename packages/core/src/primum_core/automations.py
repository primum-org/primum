"""What the automations of a package do when something happens (decision 0029).

Pure: given what happened (an event, by its id) and the values the variables have, it says
which automations act, and what an increment leaves a variable at. Whoever runs the package
does the rest: starts and stops the sequences, keeps the values.

- An automation acts when it is enabled, the event is one of its ``when``, and its condition
  holds (``primum_core.expressions``). Without a condition it always holds.
- **Every condition is worked out on the same values**: those the variables had when the
  event came, before any automation acted. Which automations act never depends on the order
  they are in. Their actions then run in the order of the package, each automation's in the
  order it lists them.
- A condition that cannot be worked out (``expressions.Failure``) does not hold; it is
  reported, with why, for whoever runs the package to tell.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from primum_core.expressions import Failure, evaluate
from primum_core.generated.model import PackageAutomation, PackageVariable
from primum_core.values import Value

DEFAULT_INCREMENT = 1
# The largest number a double holds: where a variable without a limit stops.
LARGEST = 1.7976931348623157e308


@dataclass(frozen=True)
class Verdict:
    """An automation an event concerns, and whether it acts: ``failure`` says why its
    condition could not be worked out, and then it does not."""

    automation: PackageAutomation
    failure: Failure | None = None

    @property
    def acts(self) -> bool:
        return self.failure is None


def verdicts(
    automations: Iterable[PackageAutomation], source: UUID, values: Mapping[UUID, Value]
) -> tuple[Verdict, ...]:
    """The automations that act on ``source``, in the order given, and those whose condition
    failed. One that is disabled, does not wait for ``source`` or whose condition is false
    is left out."""
    found: list[Verdict] = []
    for automation in automations:
        if not automation.enabled or source not in automation.when:
            continue
        holds = evaluate(automation.if_, values) if automation.if_ else True
        if isinstance(holds, Failure):
            found.append(Verdict(automation, holds))
        elif holds is True:
            found.append(Verdict(automation))
    return tuple(found)


def incremented(variable: PackageVariable, value: Value, by: float | None) -> Value:
    """What ``increment_variable`` leaves a numeric variable at: ``value`` plus ``by`` (1 when
    absent), held to the limits the variable has. One that would pass a limit stays at it.
    Without a limit on that side it stays a number every runtime holds."""
    if isinstance(value, bool | str):  # a package that holds together never increments one
        raise TypeError(f"{variable.name} is not a number: {value!r}")
    amount = DEFAULT_INCREMENT if by is None else by
    try:
        result = value + amount
    except OverflowError:  # a whole number no double holds, plus one with decimals
        result = LARGEST if amount > 0 else -LARGEST
    low = -LARGEST if variable.min is None else variable.min
    high = LARGEST if variable.max is None else variable.max
    return min(max(result, low), high)
