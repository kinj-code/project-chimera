"""CompanionOverlay — a frameless, always-on-top character window with painted face.

The face is drawn with QPainter. Two expressions: IDLE (neutral) and HAPPY (smiling).
MoodChange events trigger the expression switch.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from PySide6.QtWidgets import QWidget

from chimera.bridge.events import Emotion, MoodChange
from loguru import logger

if TYPE_CHECKING:
    from chimera.bridge.bus import EventBus


class CompanionOverlay(QWidget):
    """A frameless overlay with a painted robot character face."""

    SIZE = 220
    PADDING = 16

    # Colors
    BG_NEUTRAL = QColor(52, 53, 65)       # dark gray
    BG_HAPPY = QColor(46, 160, 67)         # green
    EYE_COLOR = QColor(255, 255, 255)
    MOUTH_COLOR = QColor(255, 255, 255)
    ANTENNA_COLOR = QColor(255, 180, 50)
    BORDER_IDLE = QColor(255, 255, 255, 80)
    BORDER_ACTIVE = QColor(255, 255, 255, 255)

    def __init__(self) -> None:
        super().__init__()
        self._current_emotion: Emotion = Emotion.NEUTRAL
        self._pulse_timer: QTimer | None = None
        self._pulse_phase: float = 0.0
        self._bg_color = self.BG_NEUTRAL
        self._target_bg = self.BG_NEUTRAL

        self._setup_ui()
        self._position()
        self._start_pulse()

    def attach(self, bus: EventBus) -> None:
        """Subscribe to MoodChange events."""
        bus.subscribe(MoodChange, self.on_mood_change)  # type: ignore[arg-type]
        logger.info("CompanionOverlay attached to EventBus (MoodChange)")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Chimera Companion")
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def _position(self) -> None:
        screen = self.screen()
        if screen is None:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None and app.primaryScreen() is not None:
                screen = app.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.right() - self.SIZE - 24,
                geom.bottom() - self.SIZE - 24,
            )

    # ------------------------------------------------------------------
    # Pulse animation
    # ------------------------------------------------------------------

    def _start_pulse(self) -> None:
        if self._pulse_timer is None:
            self._pulse_timer = QTimer(self)
            self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start(100)

    def _stop_pulse(self) -> None:
        if self._pulse_timer is not None:
            self._pulse_timer.stop()
            self._pulse_timer = None

    def _tick_pulse(self) -> None:
        self._pulse_phase += 0.1 / 1.5
        if self._pulse_phase > 1.0:
            self._pulse_phase = 0.0
        self.update()

    # ------------------------------------------------------------------
    # Mood handling
    # ------------------------------------------------------------------

    async def on_mood_change(self, event: MoodChange) -> None:
        self._current_emotion = event.current
        if event.current == Emotion.HAPPY:
            self._bg_color = self.BG_HAPPY
            QTimer.singleShot(2500, self._revert_to_neutral)
        else:
            self._revert_to_neutral()

    def _revert_to_neutral(self) -> None:
        self._current_emotion = Emotion.NEUTRAL
        self._bg_color = self.BG_NEUTRAL
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = QPoint(self.SIZE // 2, self.SIZE // 2)
        face_radius = self.SIZE // 2 - self.PADDING

        # --- Background circle ---
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._bg_color))
        painter.drawEllipse(center, face_radius, face_radius)

        # --- Pulsing border ---
        if self._current_emotion == Emotion.NEUTRAL:
            if self._pulse_phase <= 0.5:
                opacity = int(80 + self._pulse_phase * 2 * 175)  # 80 → 255
            else:
                opacity = int(255 - (self._pulse_phase - 0.5) * 2 * 175)
            border_color = QColor(255, 255, 255, max(30, min(255, opacity)))
        else:
            border_color = self.BORDER_ACTIVE

        pen = QPen(border_color, 3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, face_radius, face_radius)

        # --- Antenna ---
        painter.setPen(QPen(self.ANTENNA_COLOR, 3))
        painter.drawLine(
            center.x(), center.y() - face_radius + 6,
            center.x(), center.y() - face_radius - 8,
        )
        painter.setBrush(QBrush(self.ANTENNA_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            QPoint(center.x(), center.y() - face_radius - 12), 5, 5
        )

        # --- Eyes ---
        eye_size = 14
        eye_y = center.y() - 18
        left_eye_x = center.x() - 28
        right_eye_x = center.x() + 28

        # Draw eyes
        painter.setBrush(QBrush(self.EYE_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(left_eye_x, eye_y), eye_size, eye_size)
        painter.drawEllipse(QPoint(right_eye_x, eye_y), eye_size, eye_size)

        # Pupils
        pupil_size = 5
        painter.setBrush(QBrush(self._bg_color))
        painter.drawEllipse(QPoint(left_eye_x + 2, eye_y), pupil_size, pupil_size)
        painter.drawEllipse(QPoint(right_eye_x + 2, eye_y), pupil_size, pupil_size)

        # Eye shine
        shine_size = 3
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(QPoint(left_eye_x + 2, eye_y - 4), shine_size, shine_size)
        painter.drawEllipse(QPoint(right_eye_x + 2, eye_y - 4), shine_size, shine_size)

        # --- Mouth ---
        mouth_y = center.y() + 26
        painter.setPen(QPen(self.MOUTH_COLOR, 2.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._current_emotion == Emotion.HAPPY:
            # Smiling mouth — a wide arc / smile curve.
            path = QPainterPath()
            path.moveTo(center.x() - 26, mouth_y)
            path.quadTo(center.x(), mouth_y + 18, center.x() + 26, mouth_y)
            painter.drawPath(path)
        else:
            # Neutral mouth — a small straight line.
            painter.drawLine(
                center.x() - 12, mouth_y,
                center.x() + 12, mouth_y,
            )

        # --- Blush circles (when HAPPY) ---
        if self._current_emotion == Emotion.HAPPY:
            blush = QColor(255, 120, 120, 100)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(blush))
            blush_y = center.y() + 4
            painter.drawEllipse(QPoint(left_eye_x - 10, blush_y), 10, 8)
            painter.drawEllipse(QPoint(right_eye_x + 10, blush_y), 10, 8)

        painter.end()