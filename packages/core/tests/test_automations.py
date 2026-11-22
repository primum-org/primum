"""What the automations of a package do when something happens: pure, in ``core``."""

import sys
from uuid import UUID

import pytest

from primum_core import expressions
from primum_core.automations import incremented, verdicts
from primum_core.expressions import Failure
from primum_core.generated.model import ConditionStep, PackageAutomation, PackageVariable
from primum_core.values import Value

PRESSED, OPENED = UUID(int=1), UUID(int=2)
VISITS, PAUSED = UUID(int=11), UUID(int=12)


def _condition(text: str) -> tuple[ConditionStep, ...]:
    tree = expressions.parse(text)
    assert not isinstance(tree, expressions.Problem)
    program = expressions.compile_program(tree, {"visits": VISITS, "paused": PAUSED})
    return tuple(
        ConditionStep(
            value=step.get("value"),  # type: ignore[arg-type]  # built by compile_program
            variable=UUID(str(step["variable"])) if "variable" in step else None,
            op=step.get("op"),  # type: ignore[arg-type]  # one of the operators
        )
        for step in program
    )


def _automation(
    number: int, *, when: tuple[UUID, ...] = (PRESSED,), condition: str = "", enabled: bool = True
) -> PackageAutomation:
    return PackageAutomation(
        id=UUID(int=number),
        name=f"Automation {number}",
        enabled=enabled,
        when=when,
        if_=_condition(condition) if condition else (),
        do=(),
    )


def _acting(
    automations: list[PackageAutomation], source: UUID, values: dict[UUID, Value]
) -> list[tuple[int, Failure | None]]:
    return [
        (v.automation.id.int, v.failure)
        for v in verdicts(automations, source, values)
        if v.acts or v.failure is not None
    ]


def test_an_automation_whose_condition_is_false_is_concerned_and_does_not_act() -> None:
    automations = [_automation(1, condition="visits < 3"), _automation(2, when=(OPENED,))]

    [verdict] = verdicts(automations, PRESSED, {VISITS: 5, PAUSED: False})

    assert (verdict.automation.id.int, verdict.acts, verdict.failure) == (1, False, None)


def test_an_automation_acts_on_an_event_it_waits_for() -> None:
    automations = [
        _automation(1),
        _automation(2, when=(OPENED,)),
        _automation(3, when=(OPENED, PRESSED)),
    ]

    assert _acting(automations, PRESSED, {}) == [(1, None), (3, None)]


def test_a_disabled_automation_never_acts() -> None:
    assert _acting([_automation(1, enabled=False)], PRESSED, {}) == []


def test_an_automation_acts_only_if_its_condition_holds() -> None:
    automations = [
        _automation(1, condition="visits < 3"),
        _automation(2, condition="visits >= 3"),
        _automation(3, condition="not paused"),
    ]

    assert _acting(automations, PRESSED, {VISITS: 2, PAUSED: False}) == [(1, None), (3, None)]
    assert _acting(automations, PRESSED, {VISITS: 3, PAUSED: True}) == [(2, None)]


def test_a_condition_that_cannot_be_worked_out_does_not_hold_and_says_why() -> None:
    automations = [_automation(1, condition="10 / visits > 1"), _automation(2)]

    [failed, acted] = verdicts(automations, PRESSED, {VISITS: 0, PAUSED: False})

    assert (failed.acts, failed.failure) == (False, Failure("division_by_zero"))
    assert (acted.acts, acted.failure) == (True, None)


def test_the_order_given_is_the_order_they_act_in() -> None:
    automations = [_automation(3), _automation(1), _automation(2)]

    assert [number for number, _ in _acting(automations, PRESSED, {})] == [3, 1, 2]


def _variable(
    kind: str = "integer", low: float | None = None, high: float | None = None
) -> PackageVariable:
    return PackageVariable(
        id=VISITS,
        name="visits",
        type=kind,  # type: ignore[arg-type]  # a type of the schema
        initial=0,
        min=low,
        max=high,
        persistent=False,
        setting=False,
    )


@pytest.mark.parametrize(
    ("value", "by", "low", "high", "result"),
    [
        (5, None, 0, 10, 6),  # one, when it does not say how much
        (5, 3, 0, 10, 8),
        (5, -2, 0, 10, 3),
        (9, 3, 0, 10, 10),  # it stays at the limit it would pass
        (10, 1, 0, 10, 10),
        (1, -5, 0, 10, 0),
        (5, 100, None, 10, 10),
        (5, -100, None, 10, -95),  # no limit on that side
        (5, 100, 0, None, 105),
        (0.5, 0.25, 0, 1, 0.75),
        (0.9, 0.25, 0, 1, 1),
    ],
)
def test_an_increment_stays_within_the_limits_of_its_variable(
    value: float, by: float | None, low: float | None, high: float | None, result: float
) -> None:
    assert incremented(_variable("number", low, high), value, by) == result


def test_an_increment_of_a_whole_number_stays_whole() -> None:
    result = incremented(_variable(), 5, None)

    assert (result, type(result)) == (6, int)


@pytest.mark.parametrize(
    ("value", "by"), [(sys.float_info.max, sys.float_info.max), (10**400, 0.5)]
)
def test_an_increment_without_limits_never_leaves_the_numbers(value: float, by: float) -> None:
    assert incremented(_variable("number"), value, by) == sys.float_info.max
    assert incremented(_variable("number"), -value, -by) == -sys.float_info.max
