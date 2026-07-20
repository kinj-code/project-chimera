"""VoiceManager — text-to-speech using pyttsx3 (offline, cross-platform).

Subscribes to SpeakRequest on the EventBus. Runs speech synthesis in a
background thread to keep the UI responsive.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from loguru import logger

from chimera.bridge.events import SpeakRequest

if TYPE_CHECKING:
    import pyttsx3


class VoiceManager:
    """Manages text-to-speech output via pyttsx3.

    Speaks every SpeakRequest published on the EventBus. Speech runs
    in a thread to avoid blocking the Qt event loop.
    """

    def __init__(self, bus: object, enabled: bool = True) -> None:
        """Initialize the voice engine.

        Args:
            bus: The EventBus instance.
            enabled: Whether voice output is active by default.
        """
        self._bus = bus
        self._enabled = enabled
        self._engine: pyttsx3.Engine | None = None
        self._speak_lock = threading.Lock()
        logger.info("VoiceManager initialized")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def attach(self) -> None:
        """Subscribe to SpeakRequest and initialize the pyttsx3 engine."""
        self._bus.subscribe(SpeakRequest, self._on_speak_request)  # type: ignore[arg-type]
        logger.info("VoiceManager attached to EventBus (SpeakRequest)")

        # Initialize engine in a background thread (pyttsx3 init can be slow).
        await asyncio.to_thread(self._init_engine)
        logger.success("VoiceManager ready")

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable voice output at runtime.

        Args:
            enabled: True to speak, False to mute.
        """
        self._enabled = enabled
        logger.info(f"Voice enabled: {enabled}")

    # ------------------------------------------------------------------
    # Engine initialization
    # ------------------------------------------------------------------

    def _init_engine(self) -> None:
        """Initialize the pyttsx3 TTS engine. Runs in a background thread."""
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 175)  # Slightly faster than default 200
            self._engine.setProperty("volume", 0.9)
            voices = self._engine.getProperty("voices")
            if voices:
                self._engine.setProperty("voice", voices[0].id)
            logger.info("pyttsx3 engine initialized")
        except Exception as exc:
            logger.error(f"Failed to initialize pyttsx3: {exc}")
            self._engine = None

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_speak_request(self, event: SpeakRequest) -> None:
        """Handle a SpeakRequest by vocalizing the text.

        Runs pyttsx3 synthesis in a background thread to avoid
        blocking the Qt event loop.

        Args:
            event: The SpeakRequest from the EventBus.
        """
        if not self._enabled:
            logger.debug(f"Voice muted. Suppressed: '{event.text[:50]}...'")
            return

        if self._engine is None:
            logger.warning("Voice engine not initialized. Skipping speech.")
            return

        text = event.text.strip()
        if not text:
            return

        logger.info(f"Speaking: '{text[:80]}{'...' if len(text) > 80 else ''}'")

        # Run the blocking pyttsx3 call in a thread.
        await asyncio.to_thread(self._speak_blocking, text)

    def _speak_blocking(self, text: str) -> None:
        """Run engine.say() + engine.runAndWait() synchronously.

        Args:
            text: The text to speak.
        """
        if self._engine is None:
            return
        with self._speak_lock:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as exc:
                logger.error(f"Speech synthesis error: {exc}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Stop the TTS engine and release resources."""
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass
        logger.info("VoiceManager shut down")