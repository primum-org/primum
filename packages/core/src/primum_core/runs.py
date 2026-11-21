"""Which sequences are running: what starting and stopping one does (decision 0023).

``primum_core.commands`` says who commands an element given the sequences that are running;
this says which those are. The engine (phase 4) keeps the list and must agree with it:

- a sequence that does not hold stops running when its last clip ends;
- starting a sequence stops the others of its exclusive group;
- starting one that is already running restarts it: it begins again and counts as started
  last. Unless it asks to ignore that (``whenStartedAgain``): then the start does nothing;
- stopping one that is not running does nothing.

The list is in the order the sequences were started, which is what ``command_at`` breaks its
ties with. Time enters as a parameter, on the caller's clock.
"""

from collections.abc import Iterable
from uuid import UUID

from primum_core.commands import Running, Timeline, Timelines


def still_running(
    running: Iterable[Running], at_ms: int, timelines: Timelines
) -> tuple[Running, ...]:
    """The sequences of ``running`` that have not ended at ``at_ms``."""
    return tuple(run for run in running if not _ended(run, at_ms, _timeline(run, timelines)))


def start(
    running: Iterable[Running], sequence: Running, timelines: Timelines
) -> tuple[Running, ...]:
    """The sequences running once ``sequence`` is started at its ``started_ms``."""
    starting = _timeline(sequence, timelines)
    live = still_running(running, sequence.started_ms, timelines)
    already = any(run.sequence == sequence.sequence for run in live)
    if already and not starting.restarts:
        return live
    group = starting.exclusive_group
    kept = tuple(
        run
        for run in live
        if run.sequence != sequence.sequence
        and (group is None or timelines[run.sequence].exclusive_group != group)
    )
    return (*kept, sequence)


def stop(running: Iterable[Running], sequence: UUID) -> tuple[Running, ...]:
    """The sequences running once ``sequence`` (its id) is stopped."""
    return tuple(run for run in running if run.sequence != sequence)


def _ended(run: Running, at_ms: int, timeline: Timeline) -> bool:
    return timeline.end is not None and at_ms - run.started_ms >= timeline.end


def _timeline(run: Running, timelines: Timelines) -> Timeline:
    timeline = timelines.get(run.sequence)
    if timeline is None:
        raise ValueError(f"sequence {run.sequence} is not among the timelines")
    return timeline
