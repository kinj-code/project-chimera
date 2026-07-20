"""CompanionOverlay — a frameless, always-on-top window that reacts to Brain events.

Subscribes to MoodChange on the EventBus. When the mood becomes HAPPY,
the background shifts from gray to green for 2 seconds, then fades back.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget

from chimera.bridge.events import Emotion, MoodChange
from loguru import logger

if TYPE_CHECKING:
    from chimera.bridge.bus import EventBus


class CompanionOverlay(QWidget):
    """A transparent, frameless overlay window that visually represents the companion.

    Positioned at the bottom-right of the screen. Reacts to MoodChange events
    by changing its background color.
    """

    NEUTRAL_COLOR = "#444444"  # dark gray
    HAPPY_COLOR = "#22aa44"  # green
    SIZE = 200

    def __init__(self) -> None:
        super().__init__()
        self._revert_timer: QTimer | None = None

        self._setup_ui()
        self._position()

    def attach(self, bus: EventBus) -> None:
        """Subscribe to MoodChange events on the event bus.

        Must be called after the bus is started.

        Args:
            bus: The running EventBus instance.
        """
        bus.subscribe(MoodChange, self.on_mood_change)  # type: ignore[arg-type]
        logger.info("CompanionOverlay attached to EventBus (MoodChange)")

    def _setup_ui(self) -> None:
        """Configure the window flags, attributes, and layout."""
        self.setWindowTitle("Chimera Companion")
        self.setFixedSize(self.SIZE, self.SIZE)

        # Frameless, always-on-top, tool window (no taskbar entry).
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Apply the initial neutral style.
        self._apply_style(self.NEUTRAL_COLOR)

    def _position(self) -> None:
        """Place the overlay at the bottom-right of the primary screen."""
        screen = self.screen()
        if screen is None:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None and app.primaryScreen() is not None:
                screen = app.primaryScreen()

        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.right() - self.SIZE - 20,
                geom.bottom() - self.SIZE - 20,
            )

    def _apply_style(self, color: str) -> None:
        """Set the widget's background color via stylesheet."""
        self.setStyleSheet(
            f"background-color: {color}; "
            f"border-radius: 20px; "
            f"border: 2px solid rgba(255, 255, 255, 0.3);"
        )

    async def on_mood_change(self, event: MoodChange) -> None:
        """Handle a MoodChange event from the Brain.

        When HAPPY is detected, flash green for 2 seconds.
        All other emotions revert to neutral gray.

        Args:
            event: The MoodChange event from the EventBus.
        """
        if event.current == Emotion.HAPPY:
            # Switch to green.
            self._apply_style(self.HAPPY_COLOR)

            # Cancel any existing revert timer.
            if self._revert_timer is not None:
                self._revert_timer.stop()

            # Schedule a reversion to neutral after 2 seconds.
            self._revert_timer = QTimer(self)
            self._revert_timer.setSingleShot(True)
            self._revert_timer.timeout.connect(self._revert_to_neutral)
            self._revert_timer.start(2000)
        else:
            self._apply_style(self.NEUTRAL_COLOR)

    def _revert_to_neutral(self) -> None:
        """Revert the overlay background to the neutral color."""
        self._apply_style(self.NEUTRAL_COLOR)
        self._revert_timer = None