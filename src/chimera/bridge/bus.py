"""Typed asynchronous Event Bus — the backbone of the Brain–Bridge–Body topology.

Every event flows through the Bus. Publishers never know who receives their
events; subscribers never know who publishes. This decoupling makes layer
swapping, testing, and plugin architecture straightforward.

Key design decisions:
- Per-subscriber asyncio.Queue for fairness and back-pressure.
- Pydantic type filtering: subscribe(ActionIntent) only receives ActionIntents.
- Global publish for fire-and-forget; request/response for RPC-style calls.
- Graceful shutdown: flush remaining events, then close (no orphaned tasks).

Author: Project Chimera Engineering Team
Version: 1.0
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, TypeVar

from loguru import logger

from chimera.bridge.events import ChimeraEvent

# Type alias for async handler functions.
Handler = Callable[[ChimeraEvent], Coroutine[Any, Any, None]]
UnsubscribeToken = int

T = TypeVar("T", bound=ChimeraEvent)


class Subscription:
    """A single subscription: (event_type, handler, queue, token)."""

    __slots__ = ("event_type", "handler", "queue", "token")

    def __init__(
        self,
        event_type: type[ChimeraEvent],
        handler: Handler,
        token: UnsubscribeToken,
    ) -> None:
        self.event_type = event_type
        self.handler = handler
        self.queue: asyncio.Queue[ChimeraEvent] = asyncio.Queue(maxsize=1000)
        self.token = token


class EventBus:
    """Central publish/subscribe event bus.

    Usage:
        bus = EventBus()

        async def on_action(action: ActionIntent) -> None:
            print(f"Action: {action.action}")

        token = bus.subscribe(ActionIntent, on_action)
        await bus.publish(ActionIntent(action="wave"))
        bus.unsubscribe(token)
        await bus.shutdown()
    """

    def __init__(self) -> None:
        self._subscriptions: dict[UnsubscribeToken, Subscription] = {}
        self._next_token: UnsubscribeToken = 1
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, event_type: type[T], handler: Handler) -> UnsubscribeToken:
        """Register an async handler for a specific event type.

        Args:
            event_type: The Pydantic event class to subscribe to (e.g. ActionIntent).
            handler: An async callable that receives matching events.

        Returns:
            An unsubscribe token. Store this to call unsubscribe() later.

        Raises:
            RuntimeError: If the bus is not running.
        """
        if not self._running:
            raise RuntimeError("EventBus is not running. Call start() before subscribing.")

        token = self._next_token
        self._next_token += 1

        sub = Subscription(event_type=event_type, handler=handler, token=token)
        self._subscriptions[token] = sub

        # Launch a worker task that drains this subscriber's queue indefinitely.
        worker = asyncio.create_task(self._worker_loop(sub), name=f"bus-worker-{token}")
        self._workers.append(worker)

        logger.debug(f"Subscribed {event_type.__name__} → token {token}")
        return token

    def unsubscribe(self, token: UnsubscribeToken) -> None:
        """Remove a subscription by its token.

        The subscriber's queue will be drained and its worker cancelled.
        """
        sub = self._subscriptions.pop(token, None)
        if sub is None:
            logger.warning(f"Unsubscribe called with unknown token: {token}")
            return
        # Signal the worker to exit by putting a sentinel.
        sub.queue.put_nowait(_SentinelEvent())
        logger.debug(f"Unsubscribed token {token} ({sub.event_type.__name__})")

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, event: ChimeraEvent) -> None:
        """Publish an event to all matching subscribers (fire-and-forget).

        The event is enqueued for every subscriber whose event_type is
        an exact match or a superclass of the published event type.
        Delivery happens asynchronously in each subscriber's worker task.

        Args:
            event: Any ChimeraEvent instance.

        Raises:
            RuntimeError: If the bus is not running.
        """
        if not self._running:
            raise RuntimeError("EventBus is not running. Call start() before publishing.")

        delivered = 0
        for sub in self._subscriptions.values():
            if isinstance(event, sub.event_type):
                try:
                    sub.queue.put_nowait(event)
                    delivered += 1
                except asyncio.QueueFull:
                    logger.error(
                        f"Subscriber queue full for token {sub.token} "
                        f"({sub.event_type.__name__}). Dropping event {event.event_id}."
                    )
        if delivered == 0:
            logger.trace(f"No subscribers for {type(event).__name__} (id={event.event_id})")

    async def request(self, event: ChimeraEvent, timeout: float = 5.0) -> list[Any]:
        """Publish an event and collect responses (RPC-style).

        This is a convenience for cases where a publisher needs an answer.
        Subscribers respond by putting a result onto a per-call Future.

        Note: This is a simplified implementation. Production use would
        use a dedicated response bus or correlation-ID matching.

        Args:
            event: The event to publish.
            timeout: Maximum wait time for responses in seconds.

        Returns:
            List of responses from all matching subscribers.
        """
        # For now, this is a stub. Full RPC will be implemented in Sprint 2.
        logger.warning("EventBus.request() is not yet fully implemented.")
        await self.publish(event)
        return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the event bus and begin processing events."""
        async with self._lock:
            if self._running:
                return
            self._running = True
            logger.info("EventBus started.")

    async def shutdown(self, grace_period: float = 2.0) -> None:
        """Gracefully shut down: drain queues, cancel workers, clean up.

        Args:
            grace_period: Seconds to wait for workers to finish current items.
        """
        async with self._lock:
            if not self._running:
                return
            self._running = False
            logger.info("EventBus shutting down...")

        # Send sentinel to all workers.
        for sub in self._subscriptions.values():
            try:
                sub.queue.put_nowait(_SentinelEvent())
            except asyncio.QueueFull:
                pass

        # Wait for workers to finish.
        if self._workers:
            await asyncio.wait(self._workers, timeout=grace_period)

        # Cancel any stragglers.
        for worker in self._workers:
            if not worker.done():
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass

        self._workers.clear()
        self._subscriptions.clear()
        logger.info("EventBus shut down complete.")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _worker_loop(self, sub: Subscription) -> None:
        """Long-running task that drains one subscriber's queue."""
        while True:
            try:
                event = await sub.queue.get()
            except asyncio.CancelledError:
                break

            if isinstance(event, _SentinelEvent):
                break

            try:
                await sub.handler(event)
            except Exception:
                logger.exception(
                    f"Unhandled exception in subscriber {sub.token} "
                    f"({sub.event_type.__name__}) while processing {event.event_id}"
                )


# ------------------------------------------------------------------
# Internal sentinel for clean worker shutdown
# ------------------------------------------------------------------


class _SentinelEvent(ChimeraEvent):
    """Internal marker to signal a worker to exit. Never published externally."""