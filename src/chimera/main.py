"""Project Chimera — Application Entry Point.

This module bootstraps the entire Chimera application:
1. Parse CLI arguments.
2. Initialize logging (loguru).
3. Create the EventBus, StateManager, and renderer registry.
4. Launch the Qt application with qasync.
5. Show the main window / companion overlay.
6. Enter the event loop.

Usage:
    uv run chimera                    # Normal launch
    uv run chimera --safe-mode        # Force Safe Mode
    uv run chimera --profile advanced # Load a named profile
    uv run chimera --version          # Print version and exit

Author: Project Chimera Engineering Team
Version: 1.0
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger


# ------------------------------------------------------------------
# Application metadata
# ------------------------------------------------------------------

APP_NAME = "Chimera"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "A modular, renderer-agnostic AI desktop companion"


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="chimera",
        description=APP_DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
        help="Print version and exit.",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        default=False,
        help="Force Safe Mode on launch (2D renderer, offline persona, OS TTS).",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        choices=["basic", "balanced", "advanced"],
        help="Load a named configuration profile.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a custom configuration file.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging (overrides config log level).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run the Brain only, without GUI. Useful for testing and embedding.",
    )
    return parser.parse_args(argv)


# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------


def setup_logging(debug: bool = False) -> None:
    """Configure structured logging via loguru.

    Logs go to:
    - stderr (colored, compact format for development).
    - ~/.local/share/chimera/logs/chimera.log (rotation, retention).
    - The Telemetry ring buffer (wired in later by the Bridge).

    Args:
        debug: If True, force TRACE level regardless of config.
    """
    # Remove default handler.
    logger.remove()

    base_log_dir = Path.home() / ".local" / "share" / "chimera" / "logs"
    base_log_dir.mkdir(parents=True, exist_ok=True)

    # Console sink.
    logger.add(
        sys.stderr,
        level="TRACE" if debug else "INFO",
        colorize=True,
        format="<green>{time:HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
        backtrace=True,
        diagnose=True,
    )

    # File sink with rotation.
    logger.add(
        base_log_dir / "chimera.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    )

    logger.info(f"{APP_NAME} v{APP_VERSION} starting...")


# ------------------------------------------------------------------
# Signal handling
# ------------------------------------------------------------------


def install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Register graceful shutdown handlers for SIGINT and SIGTERM.

    On signal:
    1. Log the event.
    2. Schedule a ShutdownRequest on the event bus.
    3. Cancel all running tasks.
    4. Stop the event loop.
    """

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}. Shutting down gracefully...")
        # Schedule stop; let the app's shutdown coroutines run.
        loop.call_soon_threadsafe(lambda: loop.create_task(_graceful_shutdown(loop)))

    async def _graceful_shutdown(loop: asyncio.AbstractEventLoop) -> None:
        """Cancel all tasks and stop the loop."""
        tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    try:
        loop.add_signal_handler(signal.SIGINT, lambda: _handle_signal(signal.SIGINT))
        loop.add_signal_handler(signal.SIGTERM, lambda: _handle_signal(signal.SIGTERM))
    except NotImplementedError:
        # Signal handlers aren't supported on all platforms (e.g. some Windows configs).
        logger.warning("Signal handlers not available on this platform.")


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Primary entry point for the Chimera application.

    Args:
        argv: Command-line arguments (defaults to sys.argv).
    """
    args = parse_args(argv)

    # Handle --version before anything else (argparse handles this via action='version').

    setup_logging(debug=args.debug)

    if args.debug:
        logger.debug(f"CLI arguments: {args}")

    logger.info(f"Profile: {args.profile or 'default'}")
    if args.safe_mode:
        logger.warning("Safe Mode requested via CLI flag.")

    # ── Headless mode ──────────────────────────────────────────
    if args.headless:
        logger.info("Running in headless mode (no GUI).")
        asyncio.run(_run_headless(args))
        return

    # ── Full GUI mode ──────────────────────────────────────────
    try:
        from PySide6.QtWidgets import QApplication

        import qasync
    except ImportError as exc:
        logger.error(
            "PySide6 or qasync is not installed. Install with: "
            "uv pip install pyside6 qasync"
        )
        raise SystemExit(1) from exc

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ProjectChimera")

    # Integrate asyncio with Qt's event loop via qasync.
    qasync_app = qasync.QApplication(app)
    loop = qasync_app._asyncio_loop  # type: ignore[attr-defined]

    install_signal_handlers(loop)

    # Bootstrap the application.
    try:
        qasync.run(_run_gui(args))
    except Exception:
        logger.exception("Fatal error during application startup.")
        sys.exit(1)


# ------------------------------------------------------------------
# Headless runner
# ------------------------------------------------------------------


async def _run_headless(args: argparse.Namespace) -> None:
    """Run the Brain in headless mode (no GUI).

    Useful for:
    - Integration testing.
    - Embedding Chimera in another application.
    - Running as a background service.
    """
    logger.info("Headless mode activated. Brain is running.")
    # Placeholder: In Sprint 3, this boots the Brain's orchestrator
    # and waits for text input on stdin.
    logger.info("Headless mode: waiting for input (type 'exit' to quit).")
    # Simple console loop for now.
    while True:
        try:
            line = sys.stdin.readline()
        except (KeyboardInterrupt, EOFError):
            break
        if not line or line.strip().lower() in ("exit", "quit"):
            break
        logger.info(f"Received: {line.strip()}")
    logger.info("Headless mode shutting down.")


# ------------------------------------------------------------------
# GUI runner
# ------------------------------------------------------------------


async def _run_gui(args: argparse.Namespace) -> None:
    """Bootstrap and run the full GUI application.

    This orchestrates:
    1. EventBus creation and startup.
    2. StateManager load (with profile overrides).
    3. Renderer registry population.
    4. MainWindow and CompanionOverlay creation.
    5. Watchdog spawning (if enabled).
    """
    from pathlib import Path

    from chimera.bridge.bus import EventBus
    from chimera.bridge.events import ChimeraEvent
    from chimera.bridge.state import ChimeraState, StateManager

    # --- Event Bus ---
    bus = EventBus()
    await bus.start()

    async def _on_shutdown(event: ChimeraEvent) -> None:
        """Handle shutdown request."""
        logger.info("Shutdown request received. Cleaning up...")
        await bus.shutdown()

    bus.subscribe(ChimeraEvent, _on_shutdown)  # type: ignore[arg-type]

    # --- State ---
    config_path = Path.home() / ".config" / "chimera" / "state.yaml"
    if args.config:
        config_path = args.config
    state_mgr = StateManager(config_path)
    state = state_mgr.load()

    # Apply CLI overrides.
    if args.profile:
        _load_profile(state, args.profile)
    if args.safe_mode:
        state.runtime.safe_mode_triggered = True
        state.runtime.system_status = (  # type: ignore[attr-defined]
            state.runtime.SystemStatus.SAFE_MODE
        )

    logger.info(f"State loaded. Renderer: {state.companion.renderer.value}")

    # --- UI ---
    # In Sprint 1, this creates the MainWindow and CompanionOverlay.
    # For now, we launch a minimal placeholder window.
    logger.info("Launching Chimera UI (placeholder)...")

    # Import here to avoid PySide6 import at module level (allows headless import).
    from PySide6.QtWidgets import QLabel, QMainWindow

    window = QMainWindow()
    window.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
    label = QLabel("Chimera is running.\nClose this window to exit.")
    label.setStyleSheet("font-size: 18px; padding: 40px;")
    window.setCentralWidget(label)
    window.resize(500, 300)
    window.show()

    logger.success(f"{APP_NAME} v{APP_VERSION} is now running.")
    logger.info("Close the window or press Ctrl+C to exit.")

    # The qasync event loop keeps running until the QApplication quits.
    # We just yield control. The loop stays alive because Qt windows are open.


# ------------------------------------------------------------------
# Profile loader
# ------------------------------------------------------------------


def _load_profile(state: ChimeraState, profile_name: str) -> None:
    """Load a named profile from config/profiles/ and merge into state.

    Args:
        state: Current ChimeraState to update.
        profile_name: One of "basic", "balanced", "advanced".
    """
    import yaml

    profile_path = Path(__file__).parent.parent.parent / "config" / "profiles" / f"{profile_name}.yaml"
    if not profile_path.exists():
        logger.warning(f"Profile not found: {profile_path}")
        return

    try:
        raw = profile_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        # Merge: update the state with profile values (shallow merge).
        for section, values in data.items():
            if hasattr(state, section):
                section_obj = getattr(state, section)
                if isinstance(values, dict):
                    for key, val in values.items():
                        if hasattr(section_obj, key):
                            setattr(section_obj, key, val)
        logger.info(f"Profile '{profile_name}' loaded from {profile_path}")
    except (yaml.YAMLError, OSError) as exc:
        logger.error(f"Failed to load profile '{profile_name}': {exc}")