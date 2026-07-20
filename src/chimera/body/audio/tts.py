"""VoiceManager — neural TTS using Piper (local, offline, high-quality).

Piper generates WAV files from text. We play them via ffplay in a
background thread, then clean up the temp file.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from chimera.bridge.events import SpeakRequest

if TYPE_CHECKING:
    pass


class VoiceManager:
    """Manages text-to-speech output via Piper TTS + ffplay.

    Speaks every SpeakRequest published on the EventBus. Audio synthesis
    and playback run in a background thread to avoid blocking the UI.
    """

    # Default Piper voice model.
    DEFAULT_VOICE = "en_US-lessac-medium"
    VOICE_DIR = Path("assets/voices")

    def __init__(self, bus: object, enabled: bool = True) -> None:
        self._bus = bus
        self._enabled = enabled
        self._voice_path: str | None = None
        logger.info("VoiceManager initialized (Piper TTS)")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def attach(self) -> None:
        """Subscribe to SpeakRequest and download the voice model if needed."""
        self._bus.subscribe(SpeakRequest, self._on_speak_request)  # type: ignore[arg-type]
        logger.info("VoiceManager attached to EventBus (SpeakRequest)")

        # Download voice model in background.
        await asyncio.to_thread(self._ensure_voice)
        logger.success("VoiceManager ready")

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        logger.info(f"Voice enabled: {enabled}")

    # ------------------------------------------------------------------
    # Voice model download
    # ------------------------------------------------------------------

    def _ensure_voice(self) -> None:
        """Ensure the Piper voice model is downloaded locally."""
        self.VOICE_DIR.mkdir(parents=True, exist_ok=True)

        model_file = self.VOICE_DIR / f"{self.DEFAULT_VOICE}.onnx"
        config_file = self.VOICE_DIR / f"{self.DEFAULT_VOICE}.onnx.json"

        if model_file.exists() and config_file.exists():
            logger.info(f"Piper voice model found: {model_file}")
            self._voice_path = str(model_file)
            return

        logger.info(f"Downloading Piper voice model: {self.DEFAULT_VOICE}...")
        try:
            import piper.voice as piper_voice

            voices = piper_voice.PiperVoice.get_voices()
            matching = [v for v in voices if v["key"] == self.DEFAULT_VOICE]
            if matching:
                import requests

                url = matching[0]["url"]
                logger.info(f"Downloading from {url}...")
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                model_file.write_bytes(resp.content)
                logger.info(f"Voice model saved to {model_file}")
            else:
                # Fallback: use piper's built-in download.
                from pathlib import Path as _Path
                import subprocess as _sp

                logger.info("Using piper CLI to download voice model...")
                _sp.run(
                    [
                        "piper",
                        "--download_dir", str(self.VOICE_DIR),
                        "--download_voice", self.DEFAULT_VOICE,
                    ],
                    check=False,
                    timeout=120,
                )
        except Exception as exc:
            logger.error(f"Failed to download Piper voice: {exc}")

        if model_file.exists():
            self._voice_path = str(model_file)
            logger.success(f"Piper voice ready: {self._voice_path}")
        else:
            logger.error("Piper voice model not available. TTS will be silent.")

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_speak_request(self, event: SpeakRequest) -> None:
        """Handle a SpeakRequest by synthesizing and playing speech.

        Args:
            event: The SpeakRequest from the EventBus.
        """
        if not self._enabled:
            logger.debug(f"Voice muted. Suppressed: '{event.text[:50]}...'")
            return

        text = event.text.strip()
        if not text:
            return

        if not self._voice_path:
            logger.warning("No voice model available. Skipping speech.")
            return

        logger.info(f"Speaking: '{text[:80]}{'...' if len(text) > 80 else ''}'")

        # Run synthesis + playback in background thread.
        await asyncio.to_thread(self._speak_blocking, text)

    def _speak_blocking(self, text: str) -> None:
        """Synthesize WAV with Piper and play with ffplay.

        Args:
            text: The text to speak.
        """
        tmp_path: str | None = None
        try:
            import subprocess as sp

            # Synthesize to a temp WAV file.
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="chimera-piper-")
            os.close(tmp_fd)

            sp.run(
                [
                    "piper",
                    "--model", str(self._voice_path),
                    "--output_file", tmp_path,
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
                check=False,
            )

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise RuntimeError("Piper failed to generate audio")

            # Play with ffplay.
            sp.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                timeout=30,
                capture_output=True,
            )
        except FileNotFoundError:
            logger.warning("[VOICE FAILED] Piper or ffplay not found. Text: {}", text)
            print(f"[VOICE FAILED] {text}")
        except Exception as exc:
            logger.warning(f"[VOICE FAILED] {exc}. Text: {text}")
            print(f"[VOICE FAILED] {text}")
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        logger.info("VoiceManager shut down")