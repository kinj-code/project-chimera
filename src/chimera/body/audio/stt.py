"""SpeechToTextManager — voice transcription using faster-whisper.

Subscribes to ListenRequest on the EventBus. When fired, records audio
from the microphone, transcribes it with faster-whisper, and publishes
a TextInputEvent with the transcribed text.

All recording and inference runs in background threads to avoid UI freezes.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from chimera.bridge.events import ListenRequest, TextInputEvent

if TYPE_CHECKING:
    pass


class SpeechToTextManager:
    """Records and transcribes voice input using faster-whisper.

    Publishes TextInputEvent with transcribed text for the Brain to process.
    """

    # Default whisper model (tiny for speed, base for better accuracy).
    DEFAULT_MODEL = "tiny"
    SAMPLE_RATE = 16000

    def __init__(self, bus: object) -> None:
        self._bus = bus
        self._model = None
        self._model_lock = threading.Lock()
        logger.info("SpeechToTextManager initialized (faster-whisper)")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def attach(self) -> None:
        """Subscribe to ListenRequest and preload the whisper model."""
        self._bus.subscribe(ListenRequest, self._on_listen_request)  # type: ignore[arg-type]
        logger.info("SpeechToTextManager attached to EventBus (ListenRequest)")

        # Preload model in background.
        await asyncio.to_thread(self._load_model)
        logger.success("SpeechToTextManager ready")

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Load the faster-whisper model. Runs in a background thread."""
        with self._model_lock:
            if self._model is not None:
                return
            try:
                from faster_whisper import WhisperModel

                logger.info(f"Loading faster-whisper model: {self.DEFAULT_MODEL}...")
                self._model = WhisperModel(
                    self.DEFAULT_MODEL,
                    device="cpu",
                    compute_type="int8",
                )
                logger.success("faster-whisper model loaded")
            except Exception as exc:
                logger.error(f"Failed to load faster-whisper model: {exc}")
                self._model = None

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_listen_request(self, event: ListenRequest) -> None:
        """Handle a ListenRequest by recording and transcribing.

        Args:
            event: The ListenRequest with recording duration.
        """
        logger.info(f"Listening for {event.duration_s:.1f}s...")

        try:
            text = await asyncio.to_thread(self._record_and_transcribe, event.duration_s)
        except Exception as exc:
            logger.error(f"STT failed: {exc}")
            return

        if text:
            logger.info(f"Transcribed: '{text}'")
            input_event = TextInputEvent(text=text, source="voice")
            await self._bus.publish(input_event)  # type: ignore[union-attr]
        else:
            logger.warning("No speech detected or transcription empty.")

    def _record_and_transcribe(self, duration_s: float) -> str:
        """Record from microphone, save to WAV, transcribe with whisper.

        Args:
            duration_s: Recording duration in seconds.

        Returns:
            Transcribed text, or empty string on failure.
        """
        audio_data = self._record_audio(duration_s)
        if audio_data is None or len(audio_data) == 0:
            return ""

        # Save to temp WAV file.
        tmp_path: str | None = None
        try:
            import os
            import struct
            import wave

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="chimera-stt-")
            os.close(tmp_fd)

            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.SAMPLE_RATE)
                wf.writeframes(audio_data)

            # Transcribe.
            return self._transcribe(tmp_path)
        except Exception as exc:
            logger.error(f"Recording/transcription error: {exc}")
            return ""
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _record_audio(self, duration_s: float) -> bytes | None:
        """Record audio from the default microphone.

        Args:
            duration_s: Recording duration in seconds.

        Returns:
            Raw PCM audio bytes (16-bit mono), or None on failure.
        """
        try:
            import sounddevice as sd
            import numpy as np

            num_frames = int(self.SAMPLE_RATE * duration_s)
            recording = sd.rec(
                num_frames,
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="int16",
            )
            sd.wait()

            return recording.tobytes()
        except Exception as exc:
            logger.error(f"Audio recording failed: {exc}")
            return None

    def _transcribe(self, wav_path: str) -> str:
        """Transcribe a WAV file using the loaded whisper model.

        Args:
            wav_path: Path to a 16kHz mono WAV file.

        Returns:
            Transcribed text, or empty string.
        """
        if self._model is None:
            logger.error("Whisper model not loaded. Cannot transcribe.")
            return ""

        try:
            segments, _ = self._model.transcribe(wav_path, language="en")
            text = " ".join(seg.text.strip() for seg in segments)
            return text.strip()
        except Exception as exc:
            logger.error(f"Transcription failed: {exc}")
            return ""