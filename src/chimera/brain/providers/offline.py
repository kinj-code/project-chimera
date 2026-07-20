"""StubLLMProvider — a canned-response provider for the vertical-slice demo.

Subscribes to TextInputEvent on the bus, simulates thinking via
asyncio.sleep(0.4), then emits SpeakRequest + MoodChange(happy).

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import time

from loguru import logger

from chimera.bridge.events import (
    Emotion,
    MoodChange,
    SpeakRequest,
    TextInputEvent,
)


class StubLLMProvider:
    """A stub LLM provider that returns canned responses.

    In Sprint 3, this will be replaced by the full orchestrator chain
    (LocalProvider → CloudProvider → OfflineProvider). For the vertical
    slice, it demonstrates the complete Brain → Bridge → Body loop.
    """

    def __init__(self, bus: object) -> None:
        """Register on the event bus.

        Args:
            bus: The EventBus instance (typed as object to avoid circular
                 import; the caller passes the real bus).
        """
        self._bus = bus
        self._response_count: int = 0
        # Handle registration in _attach so __init__ doesn't require awaiting.

    async def attach(self) -> None:
        """Subscribe to TextInputEvent on the bus.

        Must be called after the bus is started. Separated from __init__
        because subscribe() requires the bus to be running.
        """
        self._bus.subscribe(TextInputEvent, self._on_text_input)  # type: ignore[arg-type]
        logger.info("StubLLMProvider attached to EventBus")

    async def _on_text_input(self, event: TextInputEvent) -> None:
        """Handle a user text input event.

        1. Simulate thinking (400ms sleep).
        2. Emit MoodChange(happy) to make the companion react visually.
        3. Emit SpeakRequest with a canned response.
        """
        logger.debug(f"StubLLM received: '{event.text}'")

        # Simulate LLM thinking latency.
        await asyncio.sleep(0.4)

        self._response_count += 1

        # Canned response pool.
        responses = [
            "Hello! I'm Chimera, your desktop companion.",
            "That's interesting! Tell me more.",
            "I'm here to help, though I'm just a stub for now.",
            "Beep boop! I'm thinking about what you said.",
        ]
        response_text = responses[self._response_count % len(responses)]

        # Emit mood change → CompanionOverlay changes color.
        mood = MoodChange(
            previous=Emotion.NEUTRAL,
            current=Emotion.HAPPY,
            intensity=1.0,
            transition_ms=400,
            cause="user_input",
        )
        await self._bus.publish(mood)  # type: ignore[union-attr]

        # Emit speech → MainWindow appends to chat log.
        speak = SpeakRequest(
            text=response_text,
            interrupt=False,
            emotion=Emotion.HAPPY,
        )
        await self._bus.publish(speak)  # type: ignore[union-attr]

        logger.info(f"StubLLM responded: '{response_text}'")