"""Schedules: when one happens, whether its windows are open, and what a project may not say."""

from datetime import datetime, timedelta
from uuid import UUID

import pytest

from primum_core import schedules
from primum_core.errors import CoreErrorCode
from primum_core.generated.model import PackageSchedule, PackageTime, PackageWindow
from project_builder import Ids, Project

# 2026-11-16 is a Monday.
MON, TUE, FRI, SAT, SUN = (datetime(2026, 11, day) for day in (16, 17, 20, 21, 22))


def _at(day: datetime, clock: str) -> datetime:
    hours, minutes, *seconds = (int(part) for part in clock.split(":"))
    return day.replace(hour=hours, minute=minutes, second=seconds[0] if seconds else 0)


def _schedule(
    times: list[tuple[str, str]] | None = None, windows: list[tuple[str, str, str]] | None = None
) -> PackageSchedule:
    """``times`` as (days, at) and ``windows`` as (days, from, to), days separated by spaces."""
    return PackageSchedule(
        id=UUID(int=1),
        name="Open",
        times=tuple(
            PackageTime(days=tuple(days.split()), at=at)  # type: ignore[arg-type]  # weekdays
            for days, at in times or []
        ),
        windows=tuple(
            PackageWindow(days=tuple(days.split()), from_=start, to=end)  # type: ignore[arg-type]  # weekdays
            for days, start, end in windows or []
        ),
    )


SHOP = _schedule(windows=[("mon tue", "10:00", "20:30")])
NIGHT = _schedule(windows=[("fri", "22:00", "02:00")])


@pytest.mark.parametrize(
    ("day", "clock", "is_open"),
    [
        (MON, "09:59:59", False),
        (MON, "10:00", True),  # from its start
        (MON, "20:29:59", True),
        (MON, "20:30", False),  # until its end, not included
        (TUE, "12:00", True),
        (FRI, "12:00", False),  # not one of its days
    ],
)
def test_a_window_is_open_from_its_start_until_its_end(
    day: datetime, clock: str, is_open: bool
) -> None:
    assert schedules.is_open(SHOP, _at(day, clock)) is is_open


@pytest.mark.parametrize(
    ("day", "clock", "is_open"),
    [
        (FRI, "21:59", False),
        (FRI, "22:00", True),
        (FRI, "23:59:59", True),
        (SAT, "00:00", True),  # still Friday's window
        (SAT, "01:59:59", True),
        (SAT, "02:00", False),
        (SAT, "22:30", False),  # Saturday has none of its own
        (FRI, "01:00", False),  # nor is Thursday's night open on Friday morning
    ],
)
def test_a_window_that_crosses_midnight_belongs_to_the_day_it_opens(
    day: datetime, clock: str, is_open: bool
) -> None:
    assert schedules.is_open(NIGHT, _at(day, clock)) is is_open


def test_a_window_that_starts_and_ends_at_the_same_time_is_never_open() -> None:
    empty = _schedule(windows=[("mon", "10:00", "10:00")])

    assert not schedules.is_open(empty, _at(MON, "10:00"))
    assert not schedules.is_open(empty, _at(MON, "15:00"))


def test_a_schedule_happens_when_a_window_opens() -> None:
    before, opening, inside = (_at(MON, clock) for clock in ("09:59", "10:00", "10:01"))

    assert schedules.happens(SHOP, before, opening)
    assert not schedules.happens(SHOP, opening, inside)  # once: it was open already
    assert not schedules.happens(SHOP, _at(MON, "09:00"), before)


def test_a_schedule_happens_the_first_time_the_time_is_known_inside_a_window() -> None:
    """A board that starts, or comes to know the time, with the shop open."""
    assert schedules.happens(SHOP, None, _at(MON, "15:00"))
    assert not schedules.happens(SHOP, None, _at(MON, "21:00"))


def test_a_window_that_opened_in_a_long_gap_still_happens_while_it_is_open() -> None:
    """The clock jumped from the morning into the window: the light must still come on."""
    assert schedules.happens(SHOP, _at(MON, "07:00"), _at(MON, "15:00"))
    assert not schedules.happens(SHOP, _at(MON, "07:00"), _at(MON, "21:00"))  # and closed again


LIGHTS = _schedule(times=[("mon", "20:30")])


@pytest.mark.parametrize(
    ("since", "now", "happens"),
    [
        ("20:29:00", "20:30:00", True),  # the minute it says
        ("20:29:30", "20:30:20", True),  # noticed a little late
        ("20:29:00", "20:29:59", False),
        ("20:30:00", "20:31:00", False),  # once: it was passed the time before
        ("20:29:00", "20:30:30", True),  # 90 s late at most
        ("20:28:00", "20:30:00", False),  # a longer gap: the time is lost
    ],
)
def test_a_time_happens_when_the_clock_passes_it(since: str, now: str, happens: bool) -> None:
    assert schedules.happens(LIGHTS, _at(MON, since), _at(MON, now)) is happens


def test_a_time_does_not_happen_on_a_day_it_does_not_name() -> None:
    assert not schedules.happens(LIGHTS, _at(TUE, "20:29"), _at(TUE, "20:30"))


def test_a_time_is_lost_while_the_time_is_not_known() -> None:
    assert not schedules.happens(LIGHTS, None, _at(MON, "20:30"))


def test_a_time_at_midnight_happens_as_the_day_turns() -> None:
    midnight = _schedule(times=[("tue", "00:00")])

    assert schedules.happens(midnight, _at(MON, "23:59:30"), _at(TUE, "00:00:10"))
    assert not schedules.happens(midnight, _at(SUN, "23:59:30"), _at(SUN, "23:59:50"))


def test_a_clock_that_goes_back_makes_nothing_happen() -> None:
    assert not schedules.happens(LIGHTS, _at(MON, "20:30:30"), _at(MON, "20:29:30"))


def test_a_time_passed_is_exactly_one_step_however_the_steps_fall() -> None:
    """Looking every few seconds across the time, it happens in one step and only one."""
    for step_s in (1, 7, 20, 59, 60, 89):
        now = _at(MON, "20:25")
        count = 0
        while now < _at(MON, "20:35"):
            following = now + timedelta(seconds=step_s)
            count += schedules.happens(LIGHTS, now, following)
            now = following
        assert count == 1, step_s


# --- what a project may not say --------------------------------------------------------------


def _open(project: Project, ids: Ids, **fields: object) -> Project:
    return project.add("open.sched", "schedule", ids(80), name="Open", **fields)


def _manifest(project: Project, ids: Ids, **fields: object) -> Project:
    return project.add("project.json", "project", ids(1), name="Shop window", **fields)


def test_a_project_with_schedules_says_its_time_zone(project: Project, ids: Ids) -> None:
    _open(_manifest(project, ids), ids, times=[{"days": ["mon"], "at": "08:00"}])

    assert project.found() == [
        (CoreErrorCode.PROJECT_TIME_ZONE_MISSING, {}, "project.json", "/timeZone")
    ]


def test_a_project_without_schedules_needs_no_time_zone(project: Project, ids: Ids) -> None:
    _manifest(project, ids)

    assert project.found() == []


def test_a_time_zone_that_is_not_one_is_refused_when_the_zones_are_known(
    project: Project, ids: Ids
) -> None:
    _manifest(project, ids, timeZone="Europe/Madird")
    project.time_zones = frozenset({"Europe/Madrid", "UTC"})

    assert project.found() == [
        (
            CoreErrorCode.PROJECT_TIME_ZONE_UNKNOWN,
            {"timeZone": "Europe/Madird"},
            "project.json",
            "/timeZone",
        )
    ]


def test_a_window_that_starts_and_ends_at_the_same_time_is_refused(
    project: Project, ids: Ids
) -> None:
    windows = [
        {"days": ["mon"], "from": "10:00", "to": "20:00"},
        {"days": ["sat"], "from": "09:00", "to": "09:00"},
    ]
    _open(project, ids, windows=windows)

    assert project.found() == [
        (CoreErrorCode.SCHEDULE_WINDOW_EMPTY, {"from": "09:00"}, "open.sched", "/windows/1")
    ]


def _greet(project: Project, ids: Ids, during: list[str]) -> Project:
    project.add("start.evt", "event", ids(30), name="Start", source="ui")
    project.add(
        "shop.vars",
        "variables",
        ids(60),
        constants=[],
        variables=[
            {"id": ids(61), "name": "visits", "type": "integer", "initial": 0, "setting": True}
        ],
    )
    do = [{"action": "increment_variable", "variable": "visits"}]
    fields = {"name": "Greet", "when": [ids(30)], "during": during, "do": do}
    return project.add("greet.auto", "automation", ids(31), **fields)


def test_an_automation_acts_during_schedules_that_have_windows(project: Project, ids: Ids) -> None:
    _open(project, ids, windows=[{"days": ["mon"], "from": "10:00", "to": "20:00"}])
    _greet(project, ids, [ids(80)])

    assert project.found() == []


def test_an_automation_cannot_wait_for_the_windows_of_a_schedule_without_any(
    project: Project, ids: Ids
) -> None:
    _open(project, ids, times=[{"days": ["mon"], "at": "08:00"}])
    _greet(project, ids, [ids(80)])

    assert project.found() == [
        (
            CoreErrorCode.AUTOMATION_DURING_WITHOUT_WINDOWS,
            {"schedule": "Open"},
            "greet.auto",
            "/during/0",
        )
    ]


def test_during_names_schedules_and_nothing_else(project: Project, ids: Ids) -> None:
    _greet(project, ids, [ids(30)])

    assert [(code, pointer) for code, _, _, pointer in project.found()] == [
        (CoreErrorCode.REF_WRONG_KIND, "/during/0")
    ]
