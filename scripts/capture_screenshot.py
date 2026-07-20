"""Offscreen screenshot generator for demo.

Runs the Chimera vertical slice offscreen, simulates a 'hello' input,
waits for the response, then saves a PNG of the MainWindow.
"""

import asyncio
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_SRC))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import qasync

from chimera.bridge.bus import EventBus
from chimera.brain.providers.offline import StubLLMProvider
from chimera.ui.main_window import MainWindow
from chimera.ui.companion_overlay import CompanionOverlay
from chimera.bridge.events import SpeakRequest, TextInputEvent


async def capture() -> None:
    # Offscreen Qt platform.
    app = QApplication.instance() or QApplication(["--platform", "offscreen"])
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    bus = EventBus()
    await bus.start()

    main_window = MainWindow(bus)
    main_window.show()

    overlay = CompanionOverlay()
    overlay.attach(bus)
    overlay.show()

    stub = StubLLMProvider(bus)
    await stub.attach()

    # Simulate "hello".
    await bus.publish(TextInputEvent(text="hello"))

    # Wait for the response to appear.
    response_received = asyncio.Future()

    async def _on_speak(event: SpeakRequest) -> None:
        if not response_received.done():
            response_received.set_result(None)

    bus.subscribe(SpeakRequest, _on_speak)  # type: ignore[arg-type]

    try:
        await asyncio.wait_for(response_received, timeout=10.0)
    except asyncio.TimeoutError:
        print("WARNING: Response timeout, capturing anyway.")

    # Force process events so the widget renders.
    await asyncio.sleep(0.5)
    app.processEvents()

    # Screenshot the main window.
    pixmap = main_window.grab()
    output = Path(__file__).resolve().parent.parent / "docs" / "demo_screenshot.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(output))
    print(f"Screenshot saved to {output}")

    await bus.shutdown()
    loop.stop()


if __name__ == "__main__":
    asyncio.run(capture())