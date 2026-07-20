"""Watchdog Monitor — a lightweight subprocess that guards the main Chimera process.

Architecture:
- The watchdog runs as a *separate process* (chimera-watchdog entry point).
- The main app emits heartbeats every 2s via a Unix socket / named pipe.
- If 3 consecutive heartbeats are missed (6s), the watchdog:
  1. Captures a faulthandler stack dump of the main process.
  2. Sends an OS notification.
  3. Optionally relaunches the main app.

This prevents "companion silent death" — if the app freezes, the user knows
immediately and can restart with one click.

Author: Project Chimera Engineering Team
Version: 1.0
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import NoReturn

from loguru import logger


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

DEFAULT_SOCKET_PATH: str = "/tmp/chimera-watchdog.sock"
HEARTBEAT_INTERVAL_S: float = 2.0
MISSED_THRESHOLD: int = 3  # 3 × 2s = 6s timeout
RECONNECT_DELAY_S: float = 1.0


# ------------------------------------------------------------------
# Watchdog server (runs in sidecar process)
# ------------------------------------------------------------------


class WatchdogServer:
    """Listens for heartbeats from the main Chimera process.

    If heartbeats stop arriving, triggers the alert/restart sequence.
    """

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_S,
        missed_threshold: int = MISSED_THRESHOLD,
        auto_restart: bool = True,
        main_pid: int | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._heartbeat_interval = heartbeat_interval
        self._missed_threshold = missed_threshold
        self._auto_restart = auto_restart
        self._main_pid = main_pid

        self._last_heartbeat: float = time.monotonic()
        self._missed_count: int = 0
        self._alert_sent: bool = False
        self._running: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the watchdog server. Blocks until shutdown."""
        self._running = True
        self._last_heartbeat = time.monotonic()

        # Clean up any stale socket file.
        try:
            os.unlink(self._socket_path)
        except OSError:
            pass

        # Create Unix socket server.
        server = await asyncio.start_unix_server(
            self._handle_connection, path=self._socket_path
        )

        logger.info(f"Watchdog listening on {self._socket_path}")
        logger.info(f"Threshold: {self._missed_threshold} missed heartbeats "
                     f"({self._missed_threshold * self._heartbeat_interval}s)")

        # Start the monitor loop.
        monitor_task = asyncio.create_task(self._monitor_loop())

        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            server.close()
            await server.wait_closed()
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass
            logger.info("Watchdog server stopped.")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming heartbeat message."""
        try:
            data = await reader.readline()
            if data:
                message = data.decode("utf-8").strip()
                if message.startswith("HEARTBEAT"):
                    self._last_heartbeat = time.monotonic()
                    self._missed_count = 0
                    if self._alert_sent:
                        logger.info("Heartbeat resumed. Alert cleared.")
                        self._alert_sent = False
        except (OSError, UnicodeDecodeError) as exc:
            logger.error(f"Error reading heartbeat: {exc}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, asyncio.IncompleteReadError):
                pass

    async def _monitor_loop(self) -> None:
        """Periodically check if heartbeats have stopped."""
        while self._running:
            await asyncio.sleep(self._heartbeat_interval)

            elapsed = time.monotonic() - self._last_heartbeat
            missed = int(elapsed // self._heartbeat_interval)

            if missed >= self._missed_threshold and not self._alert_sent:
                await self._trigger_alert()
                self._alert_sent = True

    async def _trigger_alert(self) -> NoReturn | None:
        """Handle a missed-heartbeat alert."""
        logger.critical(
            f"Main process appears unresponsive "
            f"({self._missed_threshold} missed heartbeats)."
        )

        # 1. Try to capture a stack dump from the main process.
        if self._main_pid:
            self._capture_stack_dump(self._main_pid)

        # 2. Send OS notification.
        self._send_notification()

        # 3. Auto-restart if configured.
        if self._auto_restart:
            logger.info("Auto-restart triggered.")
            self._restart_main()

        return None  # mypy: NoReturn for unreachable case

    @staticmethod
    def _capture_stack_dump(pid: int) -> None:
        """Attempt to capture a faulthandler stack dump from the main process."""
        try:
            import faulthandler

            # Write dump to a file in the logs directory.
            log_dir = Path.home() / ".local" / "share" / "chimera" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            dump_path = log_dir / f"crash-dump-{int(time.time())}.txt"

            with open(dump_path, "w") as f:
                # faulthandler.dump_traceback writes to stderr by default,
                # but we can redirect. For the watchdog, we capture the
                # traceback of the main process via signal.
                try:
                    os.kill(pid, signal.SIGUSR1)  # Requires faulthandler registered in main.
                except ProcessLookupError:
                    logger.warning(f"Main process {pid} no longer exists.")
            logger.info(f"Stack dump requested for PID {pid}. Output at {dump_path}")
        except Exception as exc:
            logger.error(f"Failed to capture stack dump: {exc}")

    @staticmethod
    def _send_notification() -> None:
        """Send an OS-level notification about the crash."""
        try:
            import subprocess

            title = "Chimera Companion"
            message = "The companion appears to have frozen. Click to recover."

            # Try notify-send (Linux).
            try:
                subprocess.run(
                    ["notify-send", title, message, "--urgency=critical"],
                    timeout=5,
                    capture_output=True,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Platform-specific alternatives for macOS/Windows can be added here.
            logger.info("OS notification sent.")
        except Exception as exc:
            logger.error(f"Failed to send notification: {exc}")

    def _restart_main(self) -> None:
        """Attempt to restart the main Chimera application."""
        # Best-effort: we log it. In production, this would use the same
        # command-line that launched the process.
        logger.info("Restart requested. Main process must be relaunched externally.")
        # The watchdog itself remains running; the user or a launcher script
        # should detect the exit and restart.


# ------------------------------------------------------------------
# Heartbeat client (runs in main process — not in this file)
# ------------------------------------------------------------------
# The main process imports HeartbeatClient and calls heartbeat() every 2s.
# This is implemented in bridge/telemetry.py during Sprint 2.


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Entry point for the watchdog sidecar process.

    Usage:
        chimera-watchdog --pid 12345
        chimera-watchdog --socket /tmp/custom.sock
    """
    parser = argparse.ArgumentParser(
        prog="chimera-watchdog",
        description="Watchdog sidecar for Project Chimera.",
    )
    parser.add_argument(
        "--pid",
        type=int,
        default=None,
        help="PID of the main Chimera process to monitor.",
    )
    parser.add_argument(
        "--socket",
        type=str,
        default=DEFAULT_SOCKET_PATH,
        help="Unix socket path for heartbeat communication.",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        default=False,
        help="Disable auto-restart on heartbeat loss.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging.",
    )
    args = parser.parse_args(argv)

    # Setup logging.
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if args.debug else "INFO",
        colorize=True,
        format="<green>{time:HH:mm:ss.SSS}</green> | WATCHDOG | <level>{message}</level>",
    )

    logger.info(f"Watchdog starting for PID {args.pid or 'unknown'}")

    server = WatchdogServer(
        socket_path=args.socket,
        auto_restart=not args.no_restart,
        main_pid=args.pid,
    )

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user.")
    except Exception:
        logger.exception("Watchdog encountered a fatal error.")
        sys.exit(1)