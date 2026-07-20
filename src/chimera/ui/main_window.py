"""MainWindow — the primary chat interface for Project Chimera.

Contains a QLineEdit for text input and a QTextEdit for the conversation
log. Publishes TextInputEvent on the EventBus when the user presses Enter.
Subscribes to SpeakRequest to append the companion's responses to the log.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLineEdit,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chimera.bridge.events import SpeakRequest, TextInputEvent  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from chimera.bridge.bus import EventBus


class MainWindow(QMainWindow):
    """The primary application window with chat input and log."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._bus = bus

        self._setup_ui()
        self._setup_bus()

    def _setup_ui(self) -> None:
        """Create and arrange the UI widgets."""
        self.setWindowTitle("Chimera — Chat")
        self.resize(500, 400)

        # Central widget with vertical layout.
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Chat log (read-only).
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Segoe UI", 11))
        self._log.setStyleSheet(
            "background-color: #1e1e1e; color: #e0e0e0; "
            "border: 1px solid #333; border-radius: 4px; padding: 8px;"
        )

        # Input field.
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message and press Enter...")
        self._input.setFont(QFont("Segoe UI", 12))
        self._input.setStyleSheet(
            "background-color: #2a2a2a; color: #ffffff; "
            "border: 1px solid #444; border-radius: 4px; padding: 8px;"
        )
        self._input.returnPressed.connect(self._on_send)

        layout.addWidget(self._log, stretch=1)
        layout.addWidget(self._input, stretch=0)

        # Welcome message.
        self._append_to_log("System", "Welcome to Project Chimera. Type a message to begin.")

    def _setup_bus(self) -> None:
        """Subscribe to SpeakRequest events from the Brain."""
        self._bus.subscribe(SpeakRequest, self._on_speak_request)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        """Handle the Enter key in the input field.

        Publishes a TextInputEvent on the EventBus so the Brain
        (StubLLMProvider) can process it.
        """
        text = self._input.text().strip()
        if not text:
            return

        # Display user message in the log.
        self._append_to_log("You", text)

        # Show "thinking..." placeholder — replaced when response arrives.
        self._append_thinking()

        # Clear the input field.
        self._input.clear()

        # Publish the event on the bus. The Brain will pick it up.
        event = TextInputEvent(text=text)
        import asyncio

        asyncio.ensure_future(self._bus.publish(event))

    async def _on_speak_request(self, event: SpeakRequest) -> None:
        """Handle a SpeakRequest from the Brain.

        Replaces the "thinking..." placeholder with the actual response.

        Args:
            event: The SpeakRequest event from the EventBus.
        """
        self._replace_thinking(event.text)

    # ------------------------------------------------------------------
    # Thinking placeholder
    # ------------------------------------------------------------------

    def _append_thinking(self) -> None:
        """Append a gray italic 'Chimera is thinking...' placeholder line.

        The placeholder is removed and replaced when the real response
        arrives via _replace_thinking().
        """
        formatted = (
            '<p><span style="color: #888888; font-style: italic;">'
            "Chimera is thinking...</span></p>"
        )
        self._log.append(formatted)

    def _replace_thinking(self, response_text: str) -> None:
        """Remove the last 'thinking' placeholder and append the real response.

        Args:
            response_text: The actual response from the Brain.
        """
        doc = self._log.document()
        cursor = self._log.textCursor()

        # Move to the end and select the last block (the thinking placeholder).
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.movePosition(
            cursor.MoveOperation.StartOfBlock, cursor.MoveMode.KeepAnchor
        )
        cursor.removeSelectedText()

        # Clean up any trailing newlines left behind.
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.deletePreviousChar()  # remove extra newline if present

        # Append the real response.
        self._append_to_log("Chimera", response_text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _append_to_log(self, speaker: str, message: str) -> None:
        """Append a formatted message to the chat log.

        Args:
            speaker: The display name of the speaker (e.g. "You", "Chimera").
            message: The message text.
        """
        color = "#8888ff" if speaker == "You" else "#44cc44"
        formatted = (
            f'<p><span style="color: {color}; font-weight: bold;">'
            f"{speaker}:</span> {message}</p>"
        )
        self._log.append(formatted)
