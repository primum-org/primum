"""The simulated HAL with its inputs changed from another thread, as the tests of a running
service do: the service reads on its event loop while the test changes a line."""

import select
import threading

from primum_runtime.board import load_board
from primum_runtime.hal import Claim, InputSpec, Pull, SimulatedHal

PIN = 27
CHANGES = 20_000
WAIT_S = 20  # for every change to be read: far more than it takes


def test_no_change_is_lost_between_a_thread_that_changes_an_input_and_one_that_reads() -> None:
    """A change is announced (a byte in the pipe) and queued. If the reader woke between
    the two it found nothing, emptied the pipe, and the change was never announced again:
    a service waiting for it waited for ever."""
    hal = SimulatedHal(load_board("rpi4b"))
    spec = InputSpec(pin=PIN, pull=Pull.UP, active_low=False, debounce_ms=0)
    hal.claim(Claim(outputs=[], inputs=[spec], pwms=[]))
    descriptor = hal.events_fd()
    assert descriptor is not None
    read = 0
    finished = threading.Event()

    def reader() -> None:
        nonlocal read
        while read < CHANGES:
            # As the event loop does: asleep until the descriptor says there is something.
            if not select.select([descriptor], [], [], WAIT_S)[0]:
                return  # a change was queued and never announced
            read += len(hal.read_events())
        finished.set()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    for number in range(CHANGES):
        hal.simulate_event(PIN, number % 2 == 0)

    assert finished.wait(WAIT_S), f"{read} of {CHANGES} changes were read"
    hal.close()
