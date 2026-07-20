"""ThemeManager — dynamic application theming with 4 built-in schemes.

Supports live theme switching without restart. Persists selection to
StateManager for cross-session recall.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from chimera.bridge.state import StateManager


_THEME_NEON = """
/* === CHIMERA — NEON THEME (Green/Cyan on Black) === */

QMainWindow, QDialog {
    background-color: #0d1117;
    color: #c9d1d9;
}

QMenuBar {
    background-color: #161b22;
    color: #8b949e;
    border-bottom: 1px solid #30363d;
    padding: 2px 0;
}
QMenuBar::item:selected {
    background-color: #21262d;
    color: #58a6ff;
}
QMenu {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    padding: 4px 0;
}
QMenu::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}

QGroupBox {
    color: #58a6ff;
    font-weight: bold;
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: #0d1117;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #58a6ff;
}

QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
}
QPushButton:pressed {
    background-color: #1f6feb;
}
QPushButton#primaryButton {
    background-color: #238636;
    color: #ffffff;
    border-color: #2ea043;
}
QPushButton#primaryButton:hover {
    background-color: #2ea043;
}

QLineEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #58a6ff;
}

QTextEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
}

QComboBox {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
QComboBox:hover {
    border-color: #58a6ff;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #c9d1d9;
    selection-background-color: #1f6feb;
    border: 1px solid #30363d;
}

QLabel {
    color: #8b949e;
}
QLabel#titleLabel {
    color: #58a6ff;
    font-size: 18px;
    font-weight: bold;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #30363d;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #58a6ff;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #1f6feb;
    border-radius: 3px;
}

QCheckBox {
    color: #c9d1d9;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #30363d;
    border-radius: 4px;
    background-color: #0d1117;
}
QCheckBox::indicator:checked {
    background-color: #238636;
    border-color: #2ea043;
}
"""

_THEME_CYBERPUNK = """
/* === CHIMERA — CYBERPUNK THEME (Magenta/Yellow on Dark Purple) === */

QMainWindow, QDialog {
    background-color: #1a0a2e;
    color: #e0d0ff;
}

QMenuBar {
    background-color: #2d1b4e;
    color: #d0b0ff;
    border-bottom: 1px solid #ff00ff;
    padding: 2px 0;
}
QMenuBar::item:selected {
    background-color: #4a2080;
    color: #ffdd00;
}
QMenu {
    background-color: #2d1b4e;
    color: #e0d0ff;
    border: 1px solid #ff00ff;
    padding: 4px 0;
}
QMenu::item:selected {
    background-color: #ff00ff;
    color: #1a0a2e;
}

QGroupBox {
    color: #ff00ff;
    font-weight: bold;
    border: 1px solid #ff00ff;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: #1a0a2e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #ffdd00;
}

QPushButton {
    background-color: #2d1b4e;
    color: #ffdd00;
    border: 1px solid #ff00ff;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #4a2080;
    border-color: #ffdd00;
}
QPushButton:pressed {
    background-color: #ff00ff;
}
QPushButton#primaryButton {
    background-color: #ff00ff;
    color: #1a0a2e;
    border-color: #ffdd00;
    font-weight: bold;
}
QPushButton#primaryButton:hover {
    background-color: #ff40ff;
}

QLineEdit {
    background-color: #2d1b4e;
    color: #ffdd00;
    border: 1px solid #ff00ff;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #ffdd00;
}

QTextEdit {
    background-color: #2d1b4e;
    color: #e0d0ff;
    border: 1px solid #ff00ff;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
}

QComboBox {
    background-color: #2d1b4e;
    color: #ffdd00;
    border: 1px solid #ff00ff;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
QComboBox:hover {
    border-color: #ffdd00;
}
QComboBox QAbstractItemView {
    background-color: #2d1b4e;
    color: #ffdd00;
    selection-background-color: #ff00ff;
    border: 1px solid #ff00ff;
}

QLabel {
    color: #d0b0ff;
}
QLabel#titleLabel {
    color: #ffdd00;
    font-size: 18px;
    font-weight: bold;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #4a2080;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #ff00ff;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #ffdd00;
    border-radius: 3px;
}

QCheckBox {
    color: #e0d0ff;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #ff00ff;
    border-radius: 4px;
    background-color: #2d1b4e;
}
QCheckBox::indicator:checked {
    background-color: #ff00ff;
    border-color: #ffdd00;
}
"""

_THEME_MINIMAL = """
/* === CHIMERA — MINIMAL THEME (White/Gray on Light Gray) === */

QMainWindow, QDialog {
    background-color: #f0f2f5;
    color: #1a1a2e;
}

QMenuBar {
    background-color: #ffffff;
    color: #4a4a6a;
    border-bottom: 1px solid #d0d0d0;
    padding: 2px 0;
}
QMenuBar::item:selected {
    background-color: #e0e0f0;
    color: #2a4a8a;
}
QMenu {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #d0d0d0;
    padding: 4px 0;
}
QMenu::item:selected {
    background-color: #2a4a8a;
    color: #ffffff;
}

QGroupBox {
    color: #2a4a8a;
    font-weight: bold;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #2a4a8a;
}

QPushButton {
    background-color: #ffffff;
    color: #4a4a6a;
    border: 1px solid #c0c0c0;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #e8ecf0;
    border-color: #2a4a8a;
}
QPushButton:pressed {
    background-color: #d0d8e0;
}
QPushButton#primaryButton {
    background-color: #2a4a8a;
    color: #ffffff;
    border-color: #1a3a7a;
}
QPushButton#primaryButton:hover {
    background-color: #3a5a9a;
}

QLineEdit {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c0c0c0;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #2a4a8a;
}

QTextEdit {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c0c0c0;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
}

QComboBox {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c0c0c0;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
QComboBox:hover {
    border-color: #2a4a8a;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1a1a2e;
    selection-background-color: #2a4a8a;
    border: 1px solid #c0c0c0;
}

QLabel {
    color: #6a6a8a;
}
QLabel#titleLabel {
    color: #2a4a8a;
    font-size: 18px;
    font-weight: bold;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #d0d0d0;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #2a4a8a;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #4a6aaa;
    border-radius: 3px;
}

QCheckBox {
    color: #1a1a2e;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #c0c0c0;
    border-radius: 4px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #2a4a8a;
    border-color: #1a3a7a;
}
"""

_THEME_SYSTEM = """
/* === CHIMERA — SYSTEM THEME (Default OS styling) === */
/* Empty QSS — uses native OS look and feel */
"""


class ThemeManager:
    """Manages application theming with 4 built-in schemes.

    Usage:
        mgr = ThemeManager()
        mgr.apply_theme(app, "Cyberpunk")
        current = mgr.current_theme  # "Cyberpunk"
    """

    THEMES: dict[str, str] = {
        "Neon": _THEME_NEON,
        "Cyberpunk": _THEME_CYBERPUNK,
        "Minimal": _THEME_MINIMAL,
        "System": _THEME_SYSTEM,
    }

    # Accent colors per theme for CompanionOverlay border / mood effects.
    ACCENT_COLORS: dict[str, str] = {
        "Neon": "#58a6ff",      # cyan-blue
        "Cyberpunk": "#ff00ff",  # magenta
        "Minimal": "#2a4a8a",    # slate blue
        "System": "#3498db",     # default blue
    }

    def __init__(self, state_manager: StateManager | None = None) -> None:
        self._state_mgr = state_manager
        self._current = "Neon"
        self._app: QApplication | None = None
        # Custom theme storage
        self._custom_qss: str | None = None
        self._custom_colors: dict[str, str] = {}

    @property
    def current_theme(self) -> str:
        return self._current

    @property
    def accent_color(self) -> str:
        return self.ACCENT_COLORS.get(self._current, "#58a6ff")

    def load_persisted(self) -> str:
        """Load the saved theme from StateManager, defaulting to 'Neon'."""
        if self._state_mgr is not None:
            try:
                state = self._state_mgr.load()
                saved = getattr(state.telemetry, "__theme__", None)
                if saved is None:
                    saved = getattr(state, "__theme__", "Neon")
                if saved in self.THEMES:
                    self._current = saved
                    logger.info(f"Loaded persisted theme: {saved}")
                    return saved
            except Exception:
                pass
        return "Neon"

    def persist_theme(self, theme_name: str) -> None:
        """Save the theme choice to StateManager."""
        if self._state_mgr is not None:
            try:
                state = self._state_mgr.load()
                # Store as an attribute on the telemetry section (hack-free persistence).
                state.telemetry.__theme__ = theme_name  # type: ignore[attr-defined]
                self._state_mgr.save(state)
                logger.info(f"Persisted theme: {theme_name}")
            except Exception as exc:
                logger.warning(f"Could not persist theme: {exc}")

    def apply_theme(self, app: QApplication, theme_name: str) -> None:
        """Apply a QSS theme to the entire application.

        Args:
            app: The QApplication instance.
            theme_name: One of 'Neon', 'Cyberpunk', 'Minimal', 'System', 'Custom'.
        """
        if theme_name == "Custom" and self._custom_qss:
            qss = self._custom_qss
            theme_name = "Custom"
        elif theme_name in self.THEMES:
            qss = self.THEMES[theme_name]
        else:
            logger.warning(f"Unknown theme '{theme_name}'. Falling back to Neon.")
            qss = self.THEMES["Neon"]
            theme_name = "Neon"

        app.setStyleSheet(qss)
        self._current = theme_name
        self._app = app
        logger.info(f"Theme applied: {theme_name}")

    def set_custom_theme(self, bg_color: str, accent_color: str, text_color: str, font_family: str = "Segoe UI") -> None:
        """Create and apply a custom QSS theme from color values."""
        qss = self._generate_custom_qss(bg_color, accent_color, text_color, font_family)
        self._custom_qss = qss
        self._custom_colors = {
            "bg_color": bg_color,
            "accent_color": accent_color,
            "text_color": text_color,
            "font_family": font_family,
        }
        if self._app:
            self.apply_theme(self._app, "Custom")

    def _generate_custom_qss(self, bg_color: str, accent_color: str, text_color: str, font_family: str) -> str:
        """Generate a QSS stylesheet from color values."""
        # Convert hex colors to RGB for sub-page gradients etc.
        def hex_to_rgb(h: str) -> tuple[int, int, int]:
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

        bg_rgb = hex_to_rgb(bg_color)
        accent_rgb = hex_to_rgb(accent_color)
        text_rgb = hex_to_rgb(text_color)

        # Generate a dynamic QSS based on the provided colors.
        # This is a simplified template - in practice you'd want more comprehensive theming.
        qss = f"""
/* === CHIMERA — CUSTOM THEME === */

QMainWindow, QDialog {{
    background-color: {bg_color};
    color: {text_color};
    font-family: {font_family};
}}

QMenuBar {{
    background-color: {bg_color};
    color: {text_color};
    border-bottom: 1px solid {accent_color};
    padding: 2px 0;
}}
QMenuBar::item:selected {{
    background-color: {accent_color};
    color: {bg_color};
}}
QMenu {{
    background-color: {bg_color};
    color: {text_color};
    border: 1px solid {accent_color};
    padding: 4px 0;
}}
QMenu::item:selected {{
    background-color: {accent_color};
    color: {bg_color};
}}

QGroupBox {{
    color: {accent_color};
    font-weight: bold;
    border: 1px solid {accent_color};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: {bg_color};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {accent_color};
}}

QPushButton {{
    background-color: {bg_color};
    color: {text_color};
    border: 1px solid {accent_color};
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {accent_color};
    color: {bg_color};
}}
QPushButton:pressed {{
    background-color: {accent_color};
}}
QPushButton#primaryButton {{
    background-color: {accent_color};
    color: {bg_color};
    border-color: {accent_color};
    font-weight: bold;
}}
QPushButton#primaryButton:hover {{
    background-color: {accent_color};
}}

QLineEdit {{
    background-color: {bg_color};
    color: {text_color};
    border: 1px solid {accent_color};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border-color: {accent_color};
}}

QTextEdit {{
    background-color: {bg_color};
    color: {text_color};
    border: 1px solid {accent_color};
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
}}

QComboBox {{
    background-color: {bg_color};
    color: {text_color};
    border: 1px solid {accent_color};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}}
QComboBox:hover {{
    border-color: {accent_color};
}}
QComboBox QAbstractItemView {{
    background-color: {bg_color};
    color: {text_color};
    selection-background-color: {accent_color};
    border: 1px solid {accent_color};
}}

QLabel {{
    color: {text_color};
}}
QLabel#titleLabel {{
    color: {accent_color};
    font-size: 18px;
    font-weight: bold;
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {accent_color};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {accent_color};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {accent_color};
    border-radius: 3px;
}}

QCheckBox {{
    color: {text_color};
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {accent_color};
    border-radius: 4px;
    background-color: {bg_color};
}}
QCheckBox::indicator:checked {{
    background-color: {accent_color};
    border-color: {accent_color};
}}
"""
        return qss
