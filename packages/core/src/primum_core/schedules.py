"""Schedules: when one happens, and whether its windows are open (decisions 0023 and 0030).

Pure: the time is a parameter, already in the time zone of the project. ``core`` reads no
clock and no time zone data; whoever runs a package turns its clock into that local time,
and only once the clock can be trusted.

- A **time** ("every day at 20:30") is an instant. It happens when the clock passes it.
- A **window** ("Monday to Saturday, 10:00 to 20:30") is open from its start until its end,
  the end not included. One that ends at or before the time it starts crosses midnight, and
  belongs to the day it opens: Friday 22:00 to 02:00 is open until 02:00 on Saturday.
- A schedule **happens**, and starts its automations, at each of its times and when one of
  its windows opens: when it has an open window and had none the time before.

What ``happens`` is asked is the time now and the time it was last asked (``since``). The
first time, with no ``since``, only an open window counts: the board has just come to know
the time inside it. A time of a schedule that falls in a gap longer than ``LATE`` is lost:
the board was off, did not know the time, or its clock jumped.
"""

from collections.abc import Iterable, Iterator
from dataclasses import replace
from datetime import datetime, time, timedelta
from typing import Protocol
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import Automation, Project, Schedule
from primum_core.references import LocatedContent

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # as ``datetime.weekday`` counts
# How late a time of a schedule may be noticed and still happen. Whoever runs a package
# looks every minute; past this, the time fell in a gap.
LATE = timedelta(seconds=90)


class TimeOfSchedule(Protocol):
    @property
    def days(self) -> tuple[str, ...]: ...
    @property
    def at(self) -> str: ...


class WindowOfSchedule(Protocol):
    @property
    def days(self) -> tuple[str, ...]: ...
    @property
    def from_(self) -> str: ...
    @property
    def to(self) -> str: ...


class AnySchedule(Protocol):
    """A schedule, as a project writes it or as a package carries it."""

    @property
    def times(self) -> Iterable[TimeOfSchedule]: ...
    @property
    def windows(self) -> Iterable[WindowOfSchedule]: ...


def is_open(schedule: AnySchedule, local: datetime) -> bool:
    """Whether a window of the schedule is open at ``local``, a time in the project's zone."""
    today, yesterday = DAYS[local.weekday()], DAYS[(local.weekday() - 1) % len(DAYS)]
    now = local.time()
    for window in schedule.windows:
        start, end = _time(window.from_), _time(window.to)
        if start < end:
            if today in window.days and start <= now < end:
                return True
        elif start > end and (
            (today in window.days and now >= start) or (yesterday in window.days and now < end)
        ):  # it crosses midnight
            return True
    return False


def happens(schedule: AnySchedule, since: datetime | None, now: datetime) -> bool:
    """Whether the schedule happens between ``since`` (not included) and ``now``: one of
    its windows opened, or one of its times was passed no longer than ``LATE`` ago. Both are
    local times of the project's zone; ``since`` is ``None`` the first time the time is
    known, and then only a window that is open counts."""
    if is_open(schedule, now) and (since is None or not is_open(schedule, since)):
        return True
    if since is None or not timedelta(0) < now - since <= LATE:
        return False
    return any(since < instant <= now for instant in _instants(schedule, since, now))


def _instants(schedule: AnySchedule, since: datetime, now: datetime) -> Iterator[datetime]:
    """Every time of the schedule on the days ``since`` and ``now`` are in."""
    for day in {since.date(), now.date()}:
        for moment in schedule.times:
            if DAYS[day.weekday()] in moment.days:
                yield datetime.combine(day, _time(moment.at))


def _time(written: str) -> time:
    hours, minutes = written.split(":")
    return time(int(hours), int(minutes))


def check_schedules(
    files: Iterable[LocatedContent],
    manifest: tuple[Project, Location],
    time_zones: Iterable[str] | None,
) -> Iterator[Issue]:
    """What is wrong with the schedules of a project and how it uses them:

    - ``schedule.window_empty`` (``from``): a window that starts and ends at the same time;
    - ``automation.during_without_windows`` (``schedule``): an automation that only acts
      during a schedule that has no windows, so never;
    - ``project.time_zone_missing``: schedules, and no time zone to read their times in;
    - ``project.time_zone_unknown`` (``timeZone``): a zone that is not one of
      ``time_zones``, the names whoever calls knows (``None``: not checked).
    """
    files = tuple(files)
    schedules: dict[UUID, Schedule] = {}
    for file in files:
        if not isinstance(file.content, Schedule):
            continue
        schedules[file.content.id] = file.content
        for index, window in enumerate(file.content.windows):
            if window.from_ == window.to:
                at = replace(file.location, pointer=f"/windows/{index}")
                yield Issue(CoreErrorCode.SCHEDULE_WINDOW_EMPTY, {"from": window.from_}, at)
    for file in files:
        if not isinstance(file.content, Automation):
            continue
        for index, during in enumerate(file.content.during):
            schedule = schedules.get(during)
            if schedule is not None and not schedule.windows:  # an unknown id: the references'
                at = replace(file.location, pointer=f"/during/{index}")
                params = {"schedule": schedule.name}
                yield Issue(CoreErrorCode.AUTOMATION_DURING_WITHOUT_WINDOWS, params, at)
    project, location = manifest
    at = replace(location, pointer="/timeZone")
    if project.time_zone is None:
        if schedules:
            yield Issue(CoreErrorCode.PROJECT_TIME_ZONE_MISSING, {}, at)
    elif time_zones is not None and project.time_zone not in frozenset(time_zones):
        params = {"timeZone": project.time_zone}
        yield Issue(CoreErrorCode.PROJECT_TIME_ZONE_UNKNOWN, params, at)
