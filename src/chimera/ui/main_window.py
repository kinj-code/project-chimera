"""MainWindow — the primary chat interface for Project Chimera.

Contains a QLineEdit for text input and a QTextEdit for the conversation
log. Publishes TextInputEvent on the EventBus when the user presses Enter.
Subscribes to SpeakRequest to append the companion's responses to the log.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chimera.bridge.events import SpeakRequest, TextInputEvent, ListenRequest  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from chimera.bridge.bus import EventBus


class MainWindow(QMainWindow):
    """The primary application window with chat input and log."""

    # Settings callback — set by main.py after construction.
    on_settings_requested: callable | None = None
    # Reference to LLM provider for settings changes.
    llm_provider: object | None = None
    # Reference to VoiceManager for settings changes.
    voice_manager: object | None = None
    # Reference to ThemeManager for live theme switching.
    theme_manager: object | None = None

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._bus = bus

        self._setup_ui()
        self._setup_bus()
        self._setup_menu()

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

        # Input row: text field + mic button.
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        input_row.addWidget(self._input, stretch=1)

        self._mic_button = QPushButton("🎤")
        self._mic_button.setFixedWidth(44)
        self._mic_button.setFixedHeight(44)
        self._mic_button.setToolTip("Push to Talk (5s recording)")
        self._mic_button.setStyleSheet(
            "QPushButton {"
            "  background-color: #c0392b;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 22px;"
            "  font-size: 20px;"
            "}"
            "QPushButton:hover { background-color: #e74c3c; }"
            "QPushButton:pressed { background-color: #962b22; }"
        )
        self._mic_button.clicked.connect(self._on_mic_pressed)
        input_row.addWidget(self._mic_button, stretch=0)

        layout.addWidget(self._log, stretch=1)
        layout.addLayout(input_row, stretch=0)

        # Welcome message.
        self._append_to_log("System", "Welcome to Project Chimera. Type a message to begin.")

    def _setup_bus(self) -> None:
        """Subscribe to SpeakRequest events from the Brain."""
        self._bus.subscribe(SpeakRequest, self._on_speak_request)  # type: ignore[arg-type]

    def _setup_menu(self) -> None:
        """Add a Settings action to the menu bar."""
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(
            "QMenuBar { background-color: #1a1a1a; color: #ccc; } "
            "QMenuBar::item:selected { background-color: #333; }"
        )

        file_menu = menu_bar.addMenu("&File")

        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._on_open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _on_open_settings(self) -> None:
        """Open the SettingsDialog and apply changes."""
        from chimera.ui.settings.settings_dialog import SettingsDialog

        dlg = SettingsDialog(
            parent=self,
            current_persona=getattr(self.llm_provider, '_persona', 'Friendly'),
            current_temperature=getattr(self.llm_provider, '_temperature', 0.8),
            voice_enabled=getattr(self.voice_manager, '_enabled', True),
            current_theme=getattr(self.theme_manager, 'current_theme', 'Neon'),
        )

        # Wire live theme preview callback.
        if self.theme_manager and hasattr(self.theme_manager, 'apply_theme'):
            def _live_preview(theme_name: str) -> None:
                from PySide6.QtWidgets import QApplication
                self.theme_manager.apply_theme(QApplication.instance(), theme_name)  # type: ignore[union-attr]

            dlg.on_theme_changed = _live_preview

        if dlg.exec() == dlg.DialogCode.Accepted:
            # Apply persona.
            if self.llm_provider and hasattr(self.llm_provider, 'set_persona'):
                self.llm_provider.set_persona(dlg.persona)
            # Apply temperature.
            if self.llm_provider and hasattr(self.llm_provider, 'set_temperature'):
                self.llm_provider.set_temperature(dlg.temperature)
            # Apply voice.
            if self.voice_manager and hasattr(self.voice_manager, 'set_enabled'):
                self.voice_manager.set_enabled(dlg.voice_enabled)
            # Persist theme.
            if self.theme_manager and hasattr(self.theme_manager, 'persist_theme'):
                self.theme_manager.persist_theme(dlg.theme)  # type: ignore[union-attr]
            self._append_to_log("System", "Settings updated.")

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

        Shows a speaking indicator, then replaces the "thinking..." placeholder
        with the actual response.

        Args:
            event: The SpeakRequest event from the EventBus.
        """
        # Show speaking indicator in gray italic.
        formatted = (
            '<p><span style="color: #888888; font-style: italic;">'
            "🔊 Chimera is speaking...</span></p>"
        )
        self._log.append(formatted)

        # Replace the thinking placeholder with the actual response.
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

    def _on_mic_pressed(self) -> None:
        """Handle Push-to-Talk button click.

        Publishes a ListenRequest on the EventBus. The STT manager
        will record audio, transcribe it, and publish a TextInputEvent.
        """
        import asyncio

        self._append_to_log("System", "🎤 Listening... (5 seconds)")
        asyncio.ensure_future(self._bus.publish(ListenRequest(duration_s=5.0)))

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
