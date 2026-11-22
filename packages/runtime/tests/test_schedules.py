"""Schedules on a board: the time of day makes things happen, once it can be trusted
(decision 0030). On the simulated HAL, with a clock for the time of day set by hand."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from starlette.testclient import WebSocketTestSession

from primum_core.generated.model import Package, PackageWindow
from primum_runtime import systemd
from primum_runtime.api.models import StateBody
from primum_runtime.config import parse_config
from primum_runtime.control import CLOCK_POLL_S
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.package import check_against_board
from show_service import (
    MANIFESTS,
    WAIT_S,
    Service,
    compiled,
    make_file,
    make_id,
    make_sequence,
    package,
    running,
)

MADRID = ZoneInfo("Europe/Madrid")
LED = make_id(4)
ON = make_id(30)
VISITS = make_id(61)
OPEN, CLOSE, SMALL_HOURS = make_id(80), make_id(81), make_id(82)
DAWN, LUNCH = make_id(83), make_id(84)
GO = make_id(202)
GREET = make_id(303)
EVERY_DAY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
# 2026-11-16 is a Monday; all times are of Madrid unless they say UTC.
MONDAY = "2026-11-16"


def _automation(number: int, name: str, when: str, *do: dict[str, object], **more: object) -> bytes:
    return make_file("automation", number, name=name, when=[when], do=list(do), **more)


def _document() -> dict[str, object]:
    """A Pi with an LED, on a shop's hours:

    - *Open*: a window, Monday 10:00 to 20:30. *Lights on* starts *On* when it opens;
    - *Close*: Monday at 20:30. *Lights off* stops *On*;
    - *Small hours*: Sunday at 02:30. *Count* counts a visit;
    - *Dawn*: Sunday at 03:00. *Early* starts *On*;
    - *Lunch*: a window, Monday 13:00 to 14:00, that nothing waits for;
    - *Greet*: the event *Go*, only during *Open*: counts a visit.
    """
    board = {"id": make_id(3), "name": "Pi", "model": "rpi4b"}
    led = {"id": LED, "name": "LED", "type": "digital_output", "pin": 17, "board": make_id(3)}
    visits = {"id": VISITS, "name": "visits", "type": "integer", "initial": 0, "setting": True}
    count: dict[str, object] = {"action": "increment_variable", "variable": "visits"}
    shop = [{"days": ["mon"], "from": "10:00", "to": "20:30"}]
    files = {
        "project.json": make_file("project", 1, name="Hours", timeZone="Europe/Madrid"),
        "hardware.hw": make_file("hardware", 2, boards=[board], elements=[led]),
        "shop.vars": make_file("variables", 60, constants=[], variables=[visits]),
        "on.sec": make_sequence(
            30, "On", 4, {"atMs": 0, "durationMs": 0, "action": "on"}, whenDone="hold"
        ),
        "open.sched": make_file("schedule", 80, name="Open", windows=shop),
        "close.sched": make_file(
            "schedule", 81, name="Close", times=[{"days": ["mon"], "at": "20:30"}]
        ),
        "small.sched": make_file(
            "schedule", 82, name="Small hours", times=[{"days": ["sun"], "at": "02:30"}]
        ),
        "dawn.sched": make_file(
            "schedule", 83, name="Dawn", times=[{"days": ["sun"], "at": "03:00"}]
        ),
        "lunch.sched": make_file(
            "schedule",
            84,
            name="Lunch",
            windows=[{"days": ["mon"], "from": "13:00", "to": "14:00"}],
        ),
        "early.auto": _automation(304, "Early", DAWN, {"action": "start_sequence", "sequence": ON}),
        "go.evt": make_file("event", 202, name="Go", source="ui"),
        "lights-on.auto": _automation(
            300, "Lights on", OPEN, {"action": "start_sequence", "sequence": ON}
        ),
        "lights-off.auto": _automation(
            301, "Lights off", CLOSE, {"action": "stop_sequence", "sequence": ON}
        ),
        "count.auto": _automation(302, "Count", SMALL_HOURS, count),
        "greet.auto": _automation(303, "Greet", GO, count, during=[OPEN]),
    }
    return compiled(files)


DOCUMENT = _document()


class _Wall:
    """The time of day, set by hand; not known until it is set."""

    def __init__(self) -> None:
        self.now: datetime | None = None

    def __call__(self) -> datetime | None:
        return self.now


class _Shop(Service):
    def __init__(self, loaded: Package | None = None) -> None:
        self.wall = _Wall()
        super().__init__(package(DOCUMENT) if loaded is None else loaded, self.wall)

    def at(self, local: str, day: str = MONDAY) -> None:
        """It is ``local`` in Madrid, and the service is woken, as its timer would."""
        self.wall.now = datetime.fromisoformat(f"{day} {local}").replace(tzinfo=MADRID)
        self.controller.expire()

    def at_utc(self, written: str) -> None:
        self.wall.now = datetime.fromisoformat(written).replace(tzinfo=UTC)
        self.controller.expire()

    def visits(self) -> object:
        return next(v.value for v in self.controller.state().variables if v.id == VISITS)

    def is_open(self, schedule: str = OPEN) -> bool | None:
        return next(s.open for s in self.controller.state().schedules if s.id == schedule)


@pytest.fixture
def shop() -> _Shop:
    return _Shop()


def test_a_window_that_opens_starts_its_automations_once(shop: _Shop) -> None:
    shop.at("09:59")
    before = shop.running()

    shop.at("10:00")
    opened = (shop.led, shop.running())
    shop.controller.stop_sequence(ON)
    shop.at("10:01")

    assert before == []
    assert opened == (True, ["On"])
    assert shop.running() == []  # still open: it does not happen again


def test_a_service_that_starts_inside_a_window_starts_its_automations(shop: _Shop) -> None:
    """How a light comes back after a power cut (decision 0023)."""
    asked_at_once = shop.controller.next_expiry_s()

    shop.at("15:00")

    assert asked_at_once == 0
    assert (shop.led, shop.running()) == (True, ["On"])


def test_nothing_happens_until_the_time_is_known_and_then_an_open_window_does(
    shop: _Shop,
) -> None:
    shop.controller.expire()  # the service starts; the clock has not been set
    unknown = (shop.running(), shop.controller.state().time_known, shop.is_open())

    shop.at("15:00")  # set from the network, inside the window

    assert unknown == ([], False, None)
    assert (shop.running(), shop.controller.state().time_known, shop.is_open()) == (
        ["On"],
        True,
        True,
    )


def test_a_time_of_day_starts_its_automations_when_the_clock_passes_it(shop: _Shop) -> None:
    shop.at("20:29")
    before = shop.running()

    shop.at("20:30")

    assert before == ["On"]
    assert shop.running() == []


def test_a_time_that_falls_in_a_gap_is_lost(shop: _Shop) -> None:
    """The clock jumped over 20:30, or the board was not looking: as if it had been off."""
    shop.at("20:00")

    shop.at("20:45")

    assert shop.running() == ["On"]  # nothing stopped it


def test_a_time_passed_while_the_time_was_not_known_is_lost(shop: _Shop) -> None:
    shop.at("20:00")
    shop.wall.now = None
    shop.controller.expire()

    shop.at("20:30:10")

    assert shop.running() == ["On"]


def test_times_are_read_in_the_time_zone_of_the_project(shop: _Shop) -> None:
    """Ten in Madrid in November is nine in UTC."""
    shop.at_utc("2026-11-16 08:59:30")
    before = shop.running()

    shop.at_utc("2026-11-16 09:00:00")

    assert (before, shop.running()) == ([], ["On"])


def test_the_hour_lived_twice_when_summer_time_ends_happens_once(shop: _Shop) -> None:
    """On 2026-10-25 Madrid goes from 03:00 back to 02:00: 02:30 comes twice."""
    shop.at_utc("2026-10-25 00:29:30")  # 02:29:30, summer time
    shop.at_utc("2026-10-25 00:30:10")  # 02:30:10
    first = shop.visits()

    shop.at_utc("2026-10-25 01:29:30")  # 02:29:30 again, winter time
    shop.at_utc("2026-10-25 01:30:10")  # 02:30:10 again
    shop.at_utc("2026-10-25 02:00:30")  # 03:00:30

    assert (first, shop.visits()) == (1, 1)


def test_a_time_in_the_hour_that_summer_time_skips_is_lost(shop: _Shop) -> None:
    """On 2026-03-29 Madrid goes from 02:00 straight to 03:00: there is no 02:30."""
    shop.at_utc("2026-03-29 00:59:30")  # 01:59:30

    shop.at_utc("2026-03-29 01:00:10")  # 03:00:10

    assert shop.visits() == 0


def test_a_time_right_after_the_hour_summer_time_skips_still_happens(shop: _Shop) -> None:
    """03:00 exists on 2026-03-29: it is the minute after 01:59. Only a minute of real time
    went by, whatever the clock on the wall says."""
    shop.at_utc("2026-03-29 00:59:30")  # 01:59:30
    before = shop.running()

    shop.at_utc("2026-03-29 01:00:10")  # 03:00:10

    assert (before, shop.running()) == ([], ["On"])


def test_a_time_right_after_the_hour_lived_twice_happens_once(shop: _Shop) -> None:
    shop.at_utc("2026-10-25 00:59:30")  # 02:59:30, summer time
    shop.at_utc("2026-10-25 01:00:10")  # 02:00:10, winter time: the hour starts again
    shop.at_utc("2026-10-25 01:59:30")  # 02:59:30 again
    first_pass = shop.running()

    shop.at_utc("2026-10-25 02:00:10")  # 03:00:10
    started = shop.running()
    shop.controller.stop_sequence(ON)
    shop.at_utc("2026-10-25 02:01:10")

    assert (first_pass, started, shop.running()) == ([], ["On"], [])


@pytest.mark.parametrize(
    ("start", "end"), [("02:30", "04:00"), ("02:00", "06:00"), ("03:00", "06:00")]
)
def test_a_window_that_starts_in_the_hour_summer_time_skips_still_opens(
    start: str, end: str
) -> None:
    """On 2026-03-29 there is no 02:30 in Madrid. A window from 02:30 is open at 03:00, and
    was not at 01:59: it opened, though the time counted back a minute from 03:00 is a
    02:59 that never was and that falls inside it."""
    loaded = package(DOCUMENT)
    window = PackageWindow(days=("sun",), from_=start, to=end)
    schedules = tuple(
        replace(s, windows=(window,)) if s.id == UUID(LUNCH) else s for s in loaded.schedules
    )
    early = next(a for a in loaded.automations if a.name == "Early")
    shop = _Shop(
        replace(loaded, schedules=schedules, automations=(replace(early, when=(UUID(LUNCH),)),))
    )
    shop.at_utc("2026-03-29 00:59:30")  # 01:59:30
    before = (shop.running(), shop.is_open(LUNCH))

    shop.at_utc("2026-03-29 01:00:10")  # 03:00:10

    assert before == ([], False)
    assert (shop.running(), shop.is_open(LUNCH)) == (["On"], True)


def test_a_window_open_through_the_hour_lived_twice_opens_once() -> None:
    """On 2026-10-25, a window from 02:30: it opens at 02:30 summer time, and the second
    02:30, an hour later, is not another opening."""
    loaded = package(DOCUMENT)
    window = PackageWindow(days=("sun",), from_="02:30", to="04:00")
    schedules = tuple(
        replace(s, windows=(window,)) if s.id == UUID(LUNCH) else s for s in loaded.schedules
    )
    early = next(a for a in loaded.automations if a.name == "Early")
    shop = _Shop(
        replace(loaded, schedules=schedules, automations=(replace(early, when=(UUID(LUNCH),)),))
    )
    shop.at_utc("2026-10-25 00:29:30")  # 02:29:30, summer time
    shop.at_utc("2026-10-25 00:30:10")  # 02:30:10: it opens
    opened = shop.running()
    shop.controller.stop_sequence(ON)

    for minute in ("01:00:10", "01:29:30", "01:30:10", "02:00:10", "02:30:10"):
        shop.at_utc(f"2026-10-25 {minute}")  # 02:00 to 02:30 again, then on to 03:30

    assert (opened, shop.running()) == (["On"], [])


def test_a_clock_corrected_forward_loses_the_times_it_jumps_over(shop: _Shop) -> None:
    """Not summer time: an hour of real time is missing, by the clock's own count."""
    shop.at_utc("2026-03-22 00:59:30")  # a Sunday, 01:59:30

    shop.at_utc("2026-03-22 02:30:10")  # 03:30:10: set forward

    assert shop.running() == []


def test_a_clock_set_far_back_is_taken_as_newly_known(shop: _Shop) -> None:
    shop.at("21:00")  # after closing
    shop.controller.stop_sequence(ON)

    shop.at("12:00")  # corrected by hours: it is inside the window after all

    assert shop.running() == ["On"]


def test_while_panic_is_on_a_schedule_starts_nothing_and_is_not_kept(shop: _Shop) -> None:
    shop.at("09:59")
    shop.controller.panic()

    shop.at("10:00")
    during = shop.running()
    shop.controller.release_panic()
    shop.at("10:01")

    assert (during, shop.running()) == ([], [])


def test_an_automation_acts_only_during_the_windows_it_names(shop: _Shop) -> None:
    shop.at("09:00")
    shop.controller.fire_event(GO)
    closed = shop.visits()

    shop.at("12:00")
    shop.controller.fire_event(GO)

    assert (closed, shop.visits()) == (0, 1)


def test_an_automation_that_waits_for_a_window_says_so_while_the_time_is_not_known(
    shop: _Shop,
) -> None:
    shop.controller.fire_event(GO)

    problem = next(a.problem for a in shop.controller.state().automations if a.id == GREET)
    assert shop.visits() == 0
    assert problem is not None
    assert (problem.code, dict(problem.params)) == (
        ErrorCode.AUTOMATION_CONDITION_FAILED,
        {"automation": "Greet", "reason": "time_unknown"},
    )


def test_the_schedules_are_looked_at_as_each_minute_turns(shop: _Shop) -> None:
    shop.at("10:00:20")

    assert shop.controller.next_expiry_s() == pytest.approx(40.05)


def test_while_the_time_is_not_known_the_clock_is_asked_again_soon(shop: _Shop) -> None:
    shop.controller.expire()

    assert shop.controller.next_expiry_s() == CLOCK_POLL_S


def test_listeners_are_told_when_the_time_comes_to_be_known(shop: _Shop) -> None:
    shop.controller.expire()
    shop.states.clear()

    shop.at("09:00")  # known, and nothing happens: no window is open

    assert [state.time_known for state in shop.states] == [True]


def test_a_minute_in_which_nothing_happens_tells_nobody(shop: _Shop) -> None:
    shop.at("09:00")
    shop.states.clear()

    shop.at("09:01")

    assert shop.states == []


def test_listeners_are_told_when_a_window_closes(shop: _Shop) -> None:
    """Nothing happens when a window closes, but what the state says of it changed."""
    shop.at("13:59")
    shop.states.clear()

    shop.at("14:00")

    [state] = shop.states
    assert next(s.open for s in state.schedules if s.id == LUNCH) is False


def test_the_state_says_what_the_controller_last_saw_of_the_time(shop: _Shop) -> None:
    """The time may come to be known between two looks: until the controller looks, and
    acts on it, the state does not run ahead of it."""
    shop.controller.expire()
    shop.wall.now = datetime.fromisoformat(f"{MONDAY} 15:00").replace(tzinfo=MADRID)
    ahead = shop.controller.state()

    shop.controller.expire()

    assert (ahead.time_known, [s.open for s in ahead.schedules if s.id == OPEN]) == (False, [None])
    assert (shop.controller.state().time_known, shop.is_open(), shop.led) == (True, True, True)


def test_a_package_in_a_time_zone_this_board_does_not_know_is_refused() -> None:
    elsewhere = replace(package(DOCUMENT), time_zone="Mars/Olympus_Mons")

    with pytest.raises(PrimumError) as refused:
        check_against_board(elsewhere, MANIFESTS)

    assert (refused.value.code, dict(refused.value.params)) == (
        ErrorCode.PACKAGE_TIME_ZONE_UNKNOWN,
        {"timeZone": "Mars/Olympus_Mons"},
    )


# --- the clock of the system, and the service ------------------------------------------------


def test_the_clock_is_trusted_once_the_system_has_set_it_from_the_network(tmp_path: Path) -> None:
    marker = tmp_path / "synchronized"
    now = systemd.trusted_time(trust=False, marker=marker)
    before = now()

    marker.touch()

    assert before is None
    assert isinstance(now(), datetime)


def test_a_clock_once_set_stays_trusted_while_the_service_runs(tmp_path: Path) -> None:
    """Restarting systemd-timesyncd removes its file until it next sets the clock: the
    clock is no worse for that."""
    marker = tmp_path / "synchronized"
    marker.touch()
    now = systemd.trusted_time(trust=False, marker=marker)
    now()

    marker.unlink()

    assert isinstance(now(), datetime)


def test_a_clock_taken_as_right_needs_no_file(tmp_path: Path) -> None:
    now = systemd.trusted_time(trust=True, marker=tmp_path / "synchronized")

    assert isinstance(now(), datetime)


@pytest.mark.parametrize(
    ("arguments", "env", "trusted"),
    [
        ([], {}, False),
        (["--trust-clock"], {}, True),
        ([], {"PRIMUM_TRUST_CLOCK": "1"}, True),
        (["--no-trust-clock"], {"PRIMUM_TRUST_CLOCK": "1"}, False),
    ],
)
def test_the_clock_can_be_taken_as_right_by_configuration(
    tmp_path: Path, arguments: list[str], env: dict[str, str], trusted: bool
) -> None:
    path = tmp_path / "show.package.json"
    path.write_text(json.dumps(DOCUMENT), encoding="utf-8")

    config = parse_config(["--simulate", "--package", str(path), *arguments], env)

    assert config.trust_clock is trusted


def test_a_running_service_starts_inside_a_window_without_anyone_asking(tmp_path: Path) -> None:
    """The timer of the service is armed from the start: nothing else would look at the
    schedules. The wait is bounded, so a timer never armed fails the test."""
    inside = datetime.fromisoformat(f"{MONDAY} 15:00").replace(tzinfo=MADRID)
    waiting = ThreadPoolExecutor(max_workers=1)

    def running_on(websocket: WebSocketTestSession) -> StateBody:
        while True:
            state = StateBody.model_validate(websocket.receive_json())
            if any(sequence.running for sequence in state.sequences):
                return state

    try:
        with running(tmp_path, DOCUMENT, lambda: inside) as (client, hal):
            with client.websocket_connect("/api/ws") as websocket:
                state = waiting.submit(running_on, websocket).result(timeout=WAIT_S)
            lit = hal.lines[17].active
    finally:
        waiting.shutdown(wait=False)

    assert lit
    assert state.timeKnown is True
    assert {schedule.name: schedule.open for schedule in state.schedules} == {
        "Open": True,
        "Close": False,
        "Small hours": False,
        "Dawn": False,
        "Lunch": False,
    }
