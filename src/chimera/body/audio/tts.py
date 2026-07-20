"""VoiceManager — neural TTS using Piper Python API (local, offline).

Uses piper-tts package's PiperVoice class for synthesis.
Voice model (.onnx) expected in assets/voices/.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from chimera.bridge.events import SpeakRequest

if TYPE_CHECKING:
    from piper import PiperVoice


class VoiceManager:
    """Manages text-to-speech output via Piper TTS + ffplay."""

    DEFAULT_VOICE = "en_US-lessac-medium"
    VOICE_DIR = Path("assets/voices")

    def __init__(self, bus: object, enabled: bool = True) -> None:
        self._bus = bus
        self._enabled = enabled
        self._voice: PiperVoice | None = None
        logger.info("VoiceManager initialized (Piper TTS)")

    async def attach(self) -> None:
        self._bus.subscribe(SpeakRequest, self._on_speak_request)  # type: ignore[arg-type]
        logger.info("VoiceManager attached")
        await asyncio.to_thread(self._ensure_voice)
        logger.success("VoiceManager ready")

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def _ensure_voice(self) -> None:
        if self._voice is not None:
            return
        try:
            from piper import PiperVoice
            model = self.VOICE_DIR / f"{self.DEFAULT_VOICE}.onnx"
            if not model.exists():
                logger.warning(f"Voice model not found: {model}")
                return
            self._voice = PiperVoice.load(str(model))
            logger.success(f"Piper voice loaded: {self.DEFAULT_VOICE}")
        except Exception as exc:
            logger.error(f"Failed to load Piper voice: {exc}")

    async def _on_speak_request(self, event: SpeakRequest) -> None:
        if not self._enabled:
            return
        text = event.text.strip()
        if not text or self._voice is None:
            return
        logger.info(f"Speaking: '{text[:80]}'")
        await asyncio.to_thread(self._speak_blocking, text)

    def _speak_blocking(self, text: str) -> None:
        tmp_path: str | None = None
        try:
            import subprocess as sp

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="chimera-piper-")
            os.close(tmp_fd)

            if self._voice is None:
                return

            # synthesize_wav requires an open wave.Wave_write object.
            with wave.open(tmp_path, "wb") as wav_file:
                self._voice.synthesize_wav(text, wav_file)

            if os.path.getsize(tmp_path) == 0:
                raise RuntimeError("Piper generated empty audio")

            sp.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                timeout=30,
                capture_output=True,
            )
        except FileNotFoundError:
            logger.warning("[VOICE FAILED] ffplay not found.")
        except Exception as exc:
            logger.warning(f"[VOICE FAILED] {exc}")
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def shutdown(self) -> None:
        logger.info("VoiceManager shut down")
