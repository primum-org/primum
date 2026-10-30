"""Fan-out of state changes to WebSocket clients.

Every message is a full state, so a client only needs the latest one: each subscription holds
one state, and a newer state replaces one not yet taken. A slow client never makes the
controller wait or the memory grow.
"""

import asyncio

from primum_runtime.control import State

# Put in a subscription when the broadcaster closes: there will be no more states.
_CLOSED = None


class Subscription:
    """The states published after it was created. Get one with ``StateBroadcaster.subscribe``."""

    def __init__(self, broadcaster: "StateBroadcaster") -> None:
        self._broadcaster = broadcaster
        self._slot: asyncio.Queue[State | None] = asyncio.Queue(maxsize=1)

    async def next(self) -> State | None:
        """The newest state not taken yet, waiting for one; ``None`` once the broadcaster closed."""
        return await self._slot.get()

    def offer(self, state: State | None) -> None:
        if self._slot.full():
            self._slot.get_nowait()
        self._slot.put_nowait(state)

    def close(self) -> None:
        self._broadcaster.unsubscribe(self)


class StateBroadcaster:
    """Used from the event loop's thread only (the API's handlers are all ``async``)."""

    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()

    def subscribe(self) -> Subscription:
        """Start receiving states now; call ``close`` on the subscription when done."""
        subscription = Subscription(self)
        self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        self._subscriptions.discard(subscription)

    def publish(self, state: State) -> None:
        for subscription in self._subscriptions:
            subscription.offer(state)

    def close(self) -> None:
        """End every subscription (on shutdown)."""
        for subscription in self._subscriptions:
            subscription.offer(_CLOSED)
