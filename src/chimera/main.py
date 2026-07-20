"""Project Chimera — Application Entry Point (Sprint 0 Vertical Slice).

Bootstraps: QApplication + qasync → EventBus → MainWindow + CompanionOverlay +
StubLLMProvider. The full Brain → Bridge → Body loop is demonstrated.

Usage:
    python src/chimera/main.py         # from repo root

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the src/ directory is on the Python path so `import chimera` works
# when running directly as a script (python src/chimera/main.py).
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from loguru import logger
from PySide6.QtWidgets import QApplication

import qasync


# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------


def setup_logging() -> None:
    """Minimal loguru config for the vertical-slice demo."""
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


# ------------------------------------------------------------------
# Async bootstrap
# ------------------------------------------------------------------


async def bootstrap() -> None:
    """Wire the EventBus, UI, and Brain stub together, then show windows.

    This runs on the qasync event loop after QApplication is created.
    """
    from chimera.bridge.bus import EventBus
    from chimera.brain.providers.offline import StubLLMProvider
    from chimera.ui.companion_overlay import CompanionOverlay
    from chimera.ui.main_window import MainWindow

    # 1. Create and start the EventBus.
    logger.info("Starting EventBus...")
    bus = EventBus()
    await bus.start()

    # 2. Create MainWindow → subscribes to SpeakRequest in __init__.
    logger.info("Creating MainWindow...")
    main_window = MainWindow(bus)
    main_window.show()

    # 3. Create CompanionOverlay → attach subscribes to MoodChange.
    logger.info("Creating CompanionOverlay...")
    overlay = CompanionOverlay()
    overlay.attach(bus)
    overlay.show()

    # 4. Create StubLLMProvider → attach subscribes to TextInputEvent.
    logger.info("Starting StubLLMProvider...")
    stub = StubLLMProvider(bus)
    await stub.attach()

    logger.success("Chimera vertical slice is running!")
    logger.info("Two windows should be visible: Chat + Companion overlay (bottom-right).")
    logger.info("Type a message in the Chat window and press Enter.")

    # Keep references alive to prevent garbage collection.
    # The Qt event loop keeps running until all windows are closed.
    # Store refs as attributes on the running loop so they persist.
    loop = asyncio.get_running_loop()
    loop._chimera_main_window = main_window  # type: ignore[attr-defined]
    loop._chimera_overlay = overlay  # type: ignore[attr-defined]
    loop._chimera_bus = bus  # type: ignore[attr-defined]
    loop._chimera_stub = stub  # type: ignore[attr-defined]


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------


def main() -> None:
    """Launch the Chimera vertical-slice demo."""
    setup_logging()

    logger.info("Chimera v0.1.0 — Vertical Slice Demo")
    logger.info("Initializing QApplication + qasync...")

    # Create Qt application.
    app = QApplication(sys.argv)
    app.setApplicationName("Chimera")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("ProjectChimera")

    # Create a qasync event loop and set it as the current loop.
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Schedule the bootstrap coroutine on this loop.
    loop.create_task(bootstrap())

    # Run the loop. This blocks until all windows are closed.
    logger.info("Entering event loop...")
    with loop:
        loop.run_forever()

    logger.info("Chimera shut down.")


if __name__ == "__main__":
    main()