"""OSAwarenessManager — screen capture, process listing, and app launching.

Gives Chimera eyes (screen OCR) and hands (app launching). All operations
run in background threads to keep the UI responsive.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from loguru import logger


class OSAwarenessManager:
    """Provides OS-level awareness capabilities.

    - Screen capture with OCR text extraction
    - Running process listing (user-facing apps only)
    - Application launching

    All methods that touch the filesystem or subprocess are safe to call
    from any thread. Async wrappers use asyncio.to_thread.
    """

    # Apps that system daemons typically run with — filtered out of listings.
    _SYSTEM_PROCESSES: set[str] = {
        "systemd", "dbus", "pulseaudio", "pipewire", "Xorg", "Xwayland",
        "sshd", "agetty", "NetworkManager", "wpa_supplicant", "polkitd",
        "accounts-daemon", "avahi-daemon", "cupsd", "bluetoothd",
        "kerneloops", "irqbalance", "rtkit-daemon", "upowerd",
    }

    # Common app name → executable mapping (with fallbacks).
    _APP_LAUNCHERS: dict[str, list[str]] = {
        "notepad": ["gedit", "gnome-text-editor", "mousepad", "kate", "nano"],
        "calculator": ["gnome-calculator", "mate-calc", "kcalc"],
        "browser": ["firefox", "chromium-browser", "google-chrome"],
        "explorer": ["nautilus", "nemo", "thunar", "dolphin"],
        "terminal": ["gnome-terminal", "xterm", "konsole", "xfce4-terminal"],
        "settings": ["gnome-control-center", "systemsettings"],
        "files": ["nautilus", "nemo", "thunar"],
        "text editor": ["gedit", "gnome-text-editor", "mousepad"],
        "code": ["code", "code-oss"],
    }

    def __init__(self) -> None:
        self._ocr_available: bool | None = None
        logger.info("OSAwarenessManager initialized")

    # ------------------------------------------------------------------
    # Public API — all are awaitable, all run in background threads
    # ------------------------------------------------------------------

    async def capture_screen(self, max_chars: int = 2000) -> str:
        """Capture the primary monitor and extract text via OCR.

        Args:
            max_chars: Maximum characters of OCR text to return.

        Returns:
            Extracted text, or "[OCR UNAVAILABLE]" if tesseract is not installed.
        """
        return await asyncio.to_thread(self._capture_blocking, max_chars)

    async def list_processes(self) -> str:
        """List user-facing running applications.

        Returns:
            A formatted string like "Running apps: firefox, code, gedit, ..."
        """
        return await asyncio.to_thread(self._list_blocking)

    async def launch_application(self, app_name: str) -> str:
        """Launch an application by name.

        Args:
            app_name: Common name (e.g. "notepad", "calculator", "browser").

        Returns:
            Success/failure message.
        """
        return await asyncio.to_thread(self._launch_blocking, app_name)

    # ------------------------------------------------------------------
    # Blocking implementations (thread-safe)
    # ------------------------------------------------------------------

    def _capture_blocking(self, max_chars: int) -> str:
        """Take a screenshot and run OCR. Runs in a background thread."""
        if not self._check_ocr():
            return "[OCR_UNAVAILABLE_IN_ENV]"

        tmp_path: str | None = None
        try:
            import mss

            # Capture primary monitor.
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary
                screenshot = sct.grab(monitor)

            # Save to temp PNG.
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="chimera-screen-")
            os.close(tmp_fd)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=tmp_path)

            # OCR.
            import pytesseract
            from PIL import Image

            img = Image.open(tmp_path)
            text = pytesseract.image_to_string(img)
            logger.info(f"[OCR CAPTURED: {len(text)} characters]")

            return text[:max_chars].strip() or "[No text detected on screen.]"
        except Exception as exc:
            logger.error(f"Screen capture/OCR failed: {exc}")
            return "[OCR ERROR]"
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _list_blocking(self) -> str:
        """List user-facing running processes. Runs in a background thread."""
        try:
            import psutil

            app_names: set[str] = set()
            for proc in psutil.process_iter(["name", "username"]):
                try:
                    info = proc.info
                    name = info["name"] or ""
                    username = info["username"] or ""

                    # Filter to user processes, not system daemons.
                    if not name:
                        continue
                    base = name.lower().replace(".exe", "").replace(".app", "")

                    # Skip system processes.
                    skip = False
                    for sys_proc in self._SYSTEM_PROCESSES:
                        if sys_proc.lower() in base:
                            skip = True
                            break
                    if skip:
                        continue

                    # Only include processes likely running under current user.
                    if username and "root" not in username.lower():
                        app_names.add(base)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if not app_names:
                return "No user-facing applications detected."

            sorted_apps = sorted(app_names)[:20]  # Limit to top 20.
            apps_str = ", ".join(sorted_apps)
            logger.info(f"[PROCESS LIST: {len(sorted_apps)} apps]")
            return f"Running apps: {apps_str}"
        except Exception as exc:
            logger.error(f"Process listing failed: {exc}")
            return "[PROCESS LIST UNAVAILABLE]"

    def _launch_blocking(self, app_name: str) -> str:
        """Launch an application by name. Runs in a background thread."""
        candidates = self._APP_LAUNCHERS.get(
            app_name.lower(), [app_name.lower()]
        )

        # Also try xdg-open as first attempt for anything.
        all_candidates = ["xdg-open"] + list(candidates)
        for executable in all_candidates:
            try:
                if executable == "xdg-open":
                    subprocess.Popen(
                        ["xdg-open", app_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                else:
                    subprocess.Popen(
                        [executable],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                logger.info(f"Launched {app_name} via {executable}")
                return f"✅ Opened {app_name}."
            except FileNotFoundError:
                continue
            except Exception as exc:
                logger.error(f"Failed to launch {app_name}: {exc}")
                return f"❌ Failed to open {app_name}: {exc}"

        return f"❌ Could not find '{app_name}'. Try installing it first."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_ocr(self) -> bool:
        """Check if tesseract OCR is available. Cached after first call."""
        if self._ocr_available is not None:
            return self._ocr_available

        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self._ocr_available = True
            logger.info("Tesseract OCR is available.")
        except Exception:
            self._ocr_available = False
            logger.warning(
                "Tesseract OCR is NOT available. Screen awareness will be disabled. "
                "Install tesseract-ocr package for screen reading."
            )
        return self._ocr_available