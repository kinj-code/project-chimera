"""SettingsDialog — configuration panel for persona, temperature, and voice.

A QDialog with:
- Persona dropdown (Friendly, Sarcastic, Professional)
- Temperature slider (0.0 – 1.0)
- Voice enable checkbox

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    pass


class SettingsDialog(QDialog):
    """A professional settings dialog for the Chimera companion."""

    # Callback for live theme preview. Set by caller before exec().
    on_theme_changed: callable | None = None

    def __init__(
        self,
        parent: QWidget | None = None,
        current_persona: str = "Friendly",
        current_temperature: float = 0.8,
        voice_enabled: bool = True,
        current_theme: str = "Neon",
    ) -> None:
        """Initialize the dialog.

        Args:
            parent: Parent widget.
            current_persona: Currently selected persona name.
            current_temperature: Current temperature (0.0-1.0).
            voice_enabled: Whether voice output is active.
            current_theme: Active theme name.
        """
        super().__init__(parent)
        self.setWindowTitle("Chimera Settings")
        self.setMinimumWidth(420)
        self.setModal(True)

        # Store references to the value holders.
        self._persona: str = current_persona
        self._temperature: float = current_temperature
        self._voice_enabled: bool = voice_enabled
        self._theme: str = current_theme

        # Widgets (populated in _setup_ui).
        self._persona_combo: QComboBox | None = None
        self._temperature_slider: QSlider | None = None
        self._temperature_label: QLabel | None = None
        self._voice_checkbox: QCheckBox | None = None
        self._theme_combo: QComboBox | None = None

        self._setup_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def persona(self) -> str:
        return self._persona

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def voice_enabled(self) -> bool:
        return self._voice_enabled

    @property
    def theme(self) -> str:
        return self._theme

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title.
        title = QLabel("Companion Settings")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
        )
        layout.addWidget(title)

        # --- Persona Group ---
        persona_group = QGroupBox("Persona")
        persona_group.setStyleSheet(self._group_style())
        persona_layout = QFormLayout(persona_group)
        persona_layout.setSpacing(8)

        self._persona_combo = QComboBox()
        self._persona_combo.addItems(["Friendly", "Sarcastic", "Professional"])
        self._persona_combo.setStyleSheet(self._dropdown_style())
        self._persona_combo.currentTextChanged.connect(self._on_persona_changed)

        persona_label = QLabel("Choose how Chimera speaks to you:")
        persona_label.setStyleSheet("color: #aaa;")
        persona_layout.addRow(persona_label)
        persona_layout.addRow("Style:", self._persona_combo)

        layout.addWidget(persona_group)

        # --- AI Group ---
        ai_group = QGroupBox("AI Behavior")
        ai_group.setStyleSheet(self._group_style())
        ai_layout = QFormLayout(ai_group)
        ai_layout.setSpacing(8)

        self._temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self._temperature_slider.setRange(0, 100)
        self._temperature_slider.setSingleStep(5)
        self._temperature_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._temperature_slider.setTickInterval(25)
        self._temperature_slider.setStyleSheet(self._slider_style())
        self._temperature_slider.valueChanged.connect(self._on_temperature_changed)

        self._temperature_label = QLabel("0.80")
        self._temperature_label.setStyleSheet("color: #aaa; font-family: monospace;")
        self._temperature_label.setFixedWidth(40)

        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("Deterministic"))
        temp_row.addWidget(self._temperature_slider, stretch=1)
        temp_row.addWidget(QLabel("Creative"))
        temp_row.addWidget(self._temperature_label)

        ai_layout.addRow("Temperature:", temp_row)

        layout.addWidget(ai_group)

        # --- Voice Group ---
        voice_group = QGroupBox("Voice")
        voice_group.setStyleSheet(self._group_style())
        voice_layout = QVBoxLayout(voice_group)

        self._voice_checkbox = QCheckBox("Enable voice output")
        self._voice_checkbox.setStyleSheet(
            "QCheckBox { color: #e0e0e0; font-size: 14px; } "
            "QCheckBox::indicator { width: 18px; height: 18px; }"
        )
        self._voice_checkbox.stateChanged.connect(self._on_voice_changed)

        voice_layout.addWidget(self._voice_checkbox)

        layout.addWidget(voice_group)

        # --- Appearance Group ---
        appearance_group = QGroupBox("Appearance")
        appearance_group.setStyleSheet(self._group_style())
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(8)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Neon", "Cyberpunk", "Minimal", "System"])
        self._theme_combo.setStyleSheet(self._dropdown_style())
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)

        appearance_layout.addRow("Theme:", self._theme_combo)
        layout.addWidget(appearance_group)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._button_style())
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(self._button_style(primary=True))
        save_btn.clicked.connect(self.accept)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_persona_changed(self, text: str) -> None:
        self._persona = text

    def _on_temperature_changed(self, value: int) -> None:
        self._temperature = value / 100.0
        if self._temperature_label is not None:
            self._temperature_label.setText(f"{self._temperature:.2f}")

    def _on_voice_changed(self, state: int) -> None:
        self._voice_enabled = state == Qt.CheckState.Checked.value

    def _on_theme_changed(self, text: str) -> None:
        """Live theme preview — applies instantly when dropdown changes."""
        self._theme = text
        if self.on_theme_changed is not None:
            self.on_theme_changed(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        """Populate UI from current settings values."""
        if self._persona_combo is not None:
            idx = self._persona_combo.findText(self._persona)
            if idx >= 0:
                self._persona_combo.setCurrentIndex(idx)

        if self._temperature_slider is not None:
            self._temperature_slider.setValue(int(self._temperature * 100))

        if self._voice_checkbox is not None:
            self._voice_checkbox.setChecked(self._voice_enabled)

        if self._theme_combo is not None:
            idx = self._theme_combo.findText(self._theme)
            if idx >= 0:
                self._theme_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Stylesheets
    # ------------------------------------------------------------------

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {"
            "  color: #ccc;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  border: 1px solid #444;"
            "  border-radius: 6px;"
            "  margin-top: 12px;"
            "  padding-top: 16px;"
            "}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin;"
            "  left: 12px;"
            "  padding: 0 6px;"
            "}"
        )

    @staticmethod
    def _dropdown_style() -> str:
        return (
            "QComboBox {"
            "  background-color: #2a2a2a;"
            "  color: #fff;"
            "  border: 1px solid #555;"
            "  border-radius: 4px;"
            "  padding: 6px 12px;"
            "  font-size: 13px;"
            "}"
            "QComboBox:hover { border-color: #777; }"
            "QComboBox QAbstractItemView {"
            "  background-color: #2a2a2a;"
            "  color: #fff;"
            "  selection-background-color: #3a3a3a;"
            "}"
        )

    @staticmethod
    def _slider_style() -> str:
        return (
            "QSlider::groove:horizontal {"
            "  height: 6px;"
            "  background: #444;"
            "  border-radius: 3px;"
            "}"
            "QSlider::handle:horizontal {"
            "  background: #5a9;"
            "  width: 16px;"
            "  height: 16px;"
            "  margin: -5px 0;"
            "  border-radius: 8px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "  background: #5a9;"
            "  border-radius: 3px;"
            "}"
        )

    @staticmethod
    def _button_style(primary: bool = False) -> str:
        if primary:
            return (
                "QPushButton {"
                "  background-color: #28a745;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 4px;"
                "  padding: 8px 20px;"
                "  font-size: 13px;"
                "  font-weight: bold;"
                "}"
                "QPushButton:hover { background-color: #2ec551; }"
                "QPushButton:pressed { background-color: #1e7e34; }"
            )
        return (
            "QPushButton {"
            "  background-color: #444;"
            "  color: #ccc;"
            "  border: 1px solid #555;"
            "  border-radius: 4px;"
            "  padding: 8px 20px;"
            "  font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #555; }"
        )