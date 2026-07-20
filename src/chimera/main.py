"""Project Chimera — Application Entry Point.

Wires: QApplication + qasync → EventBus → MainWindow + CompanionOverlay
+ LocalLLMProvider (Qwen2 0.5B) + VoiceManager (pyttsx3).

Usage:
    python src/chimera/main.py

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the src/ directory is on the Python path.
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from loguru import logger
from PySide6.QtWidgets import QApplication

import qasync


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        ),
    )


async def bootstrap() -> None:
    """Wire EventBus, UI, LLM, and Voice together."""
    from chimera.bridge.bus import EventBus
    from chimera.brain.providers.local import LocalLLMProvider
    from chimera.body.audio.tts import VoiceManager
    from chimera.body.audio.stt import SpeechToTextManager
    from chimera.ui.companion_overlay import CompanionOverlay
    from chimera.ui.main_window import MainWindow

    # 1. EventBus.
    logger.info("Starting EventBus...")
    bus = EventBus()
    await bus.start()

    # 2. MainWindow.
    logger.info("Creating MainWindow...")
    main_window = MainWindow(bus)
    main_window.show()

    # 3. CompanionOverlay (painted robot face).
    logger.info("Creating CompanionOverlay...")
    overlay = CompanionOverlay()
    overlay.attach(bus)
    overlay.show()

    # 4. LocalLLMProvider (real LLM with Qwen2).
    logger.info("Starting LocalLLMProvider (Qwen2 0.5B)...")
    llm = LocalLLMProvider(bus)
    await llm.attach()

    # 5. VoiceManager (Piper TTS).
    logger.info("Starting VoiceManager (Piper)...")
    voice = VoiceManager(bus)
    await voice.attach()

    # 6. SpeechToTextManager (faster-whisper).
    logger.info("Starting SpeechToTextManager (faster-whisper)...")
    stt = SpeechToTextManager(bus)
    await stt.attach()

    # Wire settings references so the MainWindow can update them.
    main_window.llm_provider = llm
    main_window.voice_manager = voice

    logger.success("Chimera is fully loaded!")
    logger.info("Chat window + Companion robot face (bottom-right) are visible.")
    logger.info("Type a message and press Enter. The AI will respond with voice.")

    # Prevent garbage collection.
    loop = asyncio.get_running_loop()
    loop._chimera_main = main_window  # type: ignore[attr-defined]
    loop._chimera_overlay = overlay  # type: ignore[attr-defined]
    loop._chimera_bus = bus  # type: ignore[attr-defined]
    loop._chimera_llm = llm  # type: ignore[attr-defined]
    loop._chimera_voice = voice  # type: ignore[attr-defined]


def main() -> None:
    setup_logging()
    logger.info("Chimera v0.2.0 — With Local LLM Brain")

    app = QApplication(sys.argv)
    app.setApplicationName("Chimera")
    app.setApplicationVersion("0.2.0")
    app.setOrganizationName("ProjectChimera")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    loop.create_task(bootstrap())

    logger.info("Entering event loop...")
    with loop:
        loop.run_forever()

    logger.info("Chimera shut down.")


if __name__ == "__main__":
    main()