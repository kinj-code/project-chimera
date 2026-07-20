"""Atomic State Manager — the canonical application state with crash-safe persistence.

Design:
- All config lives in a typed Pydantic model (ChimeraState).
- On write: serialize to a temp file, fsync, then os.replace() for atomicity.
- On read: validate against the Pydantic schema; on failure, restore from .bak,
  then from the built-in default, preserving user memories.db at all costs.
- Every mutation is logged to Telemetry for audit/debug.

Author: Project Chimera Engineering Team
Version: 1.0
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from chimera.bridge.events import Emotion, RendererMode, SystemStatus


# ------------------------------------------------------------------
# State models
# ------------------------------------------------------------------


class CompanionState(BaseModel):
    """User-facing companion configuration."""

    renderer: RendererMode = Field(default=RendererMode.SPRITE_2D)
    character: str = Field(default="default")
    scale: float = Field(default=1.0, ge=0.25, le=4.0)
    opacity: float = Field(default=0.95, ge=0.1, le=1.0)
    always_on_top: bool = True
    position_behavior: str = Field(default="remember")  # "remember" | "center" | "follow_active"
    position_x: int = 100
    position_y: int = 100


class BrainState(BaseModel):
    """Brain / AI configuration."""

    provider_chain: list[str] = Field(default=["local", "cloud", "offline"])
    local_model_path: str = ""
    local_quantization: str = "Q4_K_M"
    local_n_ctx: int = 4096
    local_n_threads: int = 4
    local_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    cloud_primary: str = "openai"
    cloud_model: str = "gpt-4o-mini"
    cloud_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    cloud_max_tokens: int = 1024
    idle_interval_ms: int = 30000
    max_gestures_per_minute: int = 6


class MemoryState(BaseModel):
    """Memory subsystem configuration."""

    short_term_max_turns: int = 20
    episodic_db_path: str = ""
    episodic_max_days: int = 90
    long_term_enabled: bool = False
    long_term_engine: str = "faiss"
    long_term_max_entries: int = 5000


class AudioState(BaseModel):
    """Audio pipeline configuration."""

    stt_engine: str = "faster-whisper"
    stt_model_size: str = "base"
    stt_device: str = "auto"
    stt_language: str = "en"
    vad_mode: str = "ptt"  # "ptt" | "ambient" | "off"
    ptt_hotkey: str = "<ctrl>+<shift>+t"
    tts_engine: str = "piper"
    tts_voice: str = "en_US-lessac-medium"
    tts_fallback: str = "os-tts"
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    output_device: str = "default"


class PerceptionState(BaseModel):
    """Screen awareness & input configuration."""

    screen_awareness_enabled: bool = False
    capture_interval_ms: int = 2000
    redaction_enabled: bool = True
    blocked_window_keywords: list[str] = Field(
        default=["*password*", "*bank*", "*1password*", "*bitwarden*", "*lastpass*", "*private*"]
    )
    capture_mouse_hover: bool = True
    capture_file_drops: bool = True


class TelemetryState(BaseModel):
    """Telemetry / logging configuration."""

    log_level: str = "INFO"
    blackbox_size: int = 10000
    flush_on_crash: bool = True
    diagnostics_sharing: str = "ask"  # "ask" | "always" | "never"


class RuntimeState(BaseModel):
    """Ephemeral runtime state — not persisted to disk."""

    system_status: SystemStatus = SystemStatus.HEALTHY
    current_emotion: Emotion = Emotion.NEUTRAL
    current_character: str = "default"
    active_renderer: RendererMode = RendererMode.SPRITE_2D
    safe_mode_triggered: bool = False
    failed_subsystems: list[str] = Field(default_factory=list)
    first_run_completed: bool = False
    uptime_s: float = 0.0


class ChimeraState(BaseModel):
    """Canonical application state — the single source of truth."""

    schema_version: int = 1
    companion: CompanionState = Field(default_factory=CompanionState)
    brain: BrainState = Field(default_factory=BrainState)
    memory: MemoryState = Field(default_factory=MemoryState)
    audio: AudioState = Field(default_factory=AudioState)
    perception: PerceptionState = Field(default_factory=PerceptionState)
    telemetry: TelemetryState = Field(default_factory=TelemetryState)
    # Runtime state is NOT persisted — it lives only in memory.
    runtime: RuntimeState = Field(default_factory=RuntimeState)


# ------------------------------------------------------------------
# State Manager
# ------------------------------------------------------------------


class StateManager:
    """Manages the canonical ChimeraState with atomic disk persistence.

    Usage:
        mgr = StateManager(Path("~/.config/chimera/state.yaml"))
        state = mgr.load()
        state.companion.renderer = RendererMode.MESH_3D
        mgr.save(state)
    """

    def __init__(self, state_path: Path | None = None) -> None:
        """Initialize the state manager.

        Args:
            state_path: Path to the state YAML file. Defaults to
                        ~/.config/chimera/state.yaml.
        """
        if state_path is None:
            base = Path.home() / ".config" / "chimera"
            state_path = base / "state.yaml"
        self._path: Path = state_path
        self._backup_path: Path = state_path.with_suffix(".yaml.bak")
        self._default_state: ChimeraState = ChimeraState()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> ChimeraState:
        """Load state from disk, with fallback chain on corruption.

        Fallback order:
        1. Primary state file (self._path).
        2. Backup state file (self._path.bak).
        3. Built-in default (ChimeraState()).

        In all cases, the user's episodic memory database (memories.db)
        path is preserved — we never touch that during state recovery.

        Returns:
            A validated ChimeraState instance.
        """
        # Try primary.
        state = self._try_load(self._path)
        if state is not None:
            return state

        # Try backup.
        logger.warning("Primary state file corrupt or missing. Trying backup.")
        state = self._try_load(self._backup_path)
        if state is not None:
            return state

        # Fall back to default.
        logger.error(
            "Both primary and backup state files are corrupt or missing. "
            "Falling back to built-in defaults. User settings have been reset."
        )
        return self._default_state.model_copy(deep=True)

    def save(self, state: ChimeraState) -> None:
        """Atomically persist state to disk.

        Steps:
        1. Serialize to a temporary file in the same directory.
        2. Fsync the temp file.
        3. os.replace() to atomically swap with the primary.
        4. (Optional) copy to backup.

        Args:
            state: The ChimeraState to persist.
        """
        # Ensure parent directory exists.
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize.
        data = self._serialize(state)

        # Write to temp file, fsync, then atomic replace.
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent), prefix="chimera-state-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
            logger.debug(f"State saved to {self._path}")
        except Exception:
            # Clean up temp file on failure.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # Also save a backup copy (best-effort).
        try:
            self._backup_path.write_text(data, encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Failed to write backup state: {exc}")

    def export_runtime_snapshot(self, state: ChimeraState) -> dict[str, Any]:
        """Export a JSON-safe snapshot for diagnostics export.

        Args:
            state: The current ChimeraState.

        Returns:
            A dict suitable for JSON serialization (all secrets redacted).
        """
        raw = state.model_dump(mode="json")
        # Redact sensitive paths.
        if "brain" in raw and "local_model_path" in raw["brain"]:
            raw["brain"]["local_model_path"] = "[REDACTED]"
        return raw

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _try_load(self, path: Path) -> ChimeraState | None:
        """Attempt to load and validate state from a path. Returns None on failure."""
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw) or {}
            return ChimeraState.model_validate(data)
        except (ValidationError, yaml.YAMLError, OSError) as exc:
            logger.error(f"Failed to load state from {path}: {exc}")
            return None

    @staticmethod
    def _serialize(state: ChimeraState) -> str:
        """Serialize state to a YAML string, excluding runtime fields."""
        # Exclude runtime state from persistence.
        data = state.model_dump(exclude={"runtime"}, mode="python")
        return yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)