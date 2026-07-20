"""VoiceManager — text-to-speech using gTTS (Google Text-to-Speech).

Subscribes to SpeakRequest on the EventBus. Generates speech via gTTS API,
saves to a temp MP3, plays with ffplay, then cleans up.

Falls back gracefully to console logging if voice generation fails
(e.g. no internet connection).

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from typing import TYPE_CHECKING

from loguru import logger

from chimera.bridge.events import SpeakRequest

if TYPE_CHECKING:
    pass


class VoiceManager:
    """Manages text-to-speech output via gTTS + ffplay.

    Speaks every SpeakRequest published on the EventBus. Audio generation
    and playback run in a background thread to avoid blocking the Qt event loop.
    """

    def __init__(self, bus: object, enabled: bool = True) -> None:
        """Initialize the voice manager.

        Args:
            bus: The EventBus instance.
            enabled: Whether voice output is active by default.
        """
        self._bus = bus
        self._enabled = enabled
        logger.info("VoiceManager initialized (gTTS + ffplay)")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def attach(self) -> None:
        """Subscribe to SpeakRequest on the EventBus."""
        self._bus.subscribe(SpeakRequest, self._on_speak_request)  # type: ignore[arg-type]
        logger.info("VoiceManager attached to EventBus (SpeakRequest)")

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable voice output at runtime.

        Args:
            enabled: True to speak, False to mute.
        """
        self._enabled = enabled
        logger.info(f"Voice enabled: {enabled}")

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_speak_request(self, event: SpeakRequest) -> None:
        """Handle a SpeakRequest by generating and playing audio.

        Runs gTTS generation + ffplay playback in a background thread.

        Args:
            event: The SpeakRequest from the EventBus.
        """
        if not self._enabled:
            logger.debug(f"Voice muted. Suppressed: '{event.text[:50]}...'")
            return

        text = event.text.strip()
        if not text:
            return

        logger.info(f"Speaking: '{text[:80]}{'...' if len(text) > 80 else ''}'")

        # Run in background thread to avoid blocking the Qt event loop.
        await asyncio.to_thread(self._speak_blocking, text)

    def _speak_blocking(self, text: str) -> None:
        """Generate MP3 with gTTS and play with ffplay.

        Args:
            text: The text to speak.
        """
        tmp_path: str | None = None
        try:
            from gtts import gTTS

            # Generate MP3 to a temp file.
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="chimera-tts-")
            os.close(tmp_fd)

            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(tmp_path)

            # Play with ffplay (suppresses video window, quiet output).
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                timeout=30,
                capture_output=True,
            )
        except FileNotFoundError:
            logger.warning("[VOICE FAILED] ffplay not found. Text: {}", text)
            print(f"[VOICE FAILED] {text}")
        except Exception as exc:
            logger.warning(f"[VOICE FAILED] {exc}. Text: {text}")
            print(f"[VOICE FAILED] {text}")
        finally:
            # Clean up temp file.
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Release resources (no-op for gTTS)."""
        logger.info("VoiceManager shut down")