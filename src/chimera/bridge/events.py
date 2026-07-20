"""Event schemas for the Chimera Event Bus.

Every event that flows through the Bridge is a Pydantic BaseModel. This gives us:
1. Strict validation — malformed events are caught at publish, not deep in a handler.
2. Auto-generated JSON Schema — useful for debugging, documentation, and future network transport.
3. Immutability-friendly — events are frozen by convention (use model_copy for mutations).

Author: Project Chimera Engineering Team
Version: 1.0
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------


class Emotion(StrEnum):
    """Abstract emotions emitted by the Brain. Persona files map these to
    concrete assets (sprites, morph targets, animation clips)."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    CURIOUS = "curious"
    ANNOYED = "annoyed"
    THINKING = "thinking"
    SURPRISED = "surprised"
    APOLOGETIC = "apologetic"
    EXCITED = "excited"
    SLEEPY = "sleepy"


class ActionKind(StrEnum):
    """Actions the companion can perform. These are abstract; the Bridge
    translates them into concrete RenderCommands per the active renderer."""

    IDLE = "idle"
    WAVE = "wave"
    POINT = "point"
    MOVE_TO = "move_to"
    GAZE_AT = "gaze_at"
    EMOTE = "emote"
    SLEEP = "sleep"
    WAKE = "wake"
    FIDGET = "fidget"
    PICK_UP = "pick_up"  # e.g. pick up a dropped file visually


class EventSeverity(StrEnum):
    """Severity levels for TelemetryEvent and logging."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RendererMode(StrEnum):
    """Active renderer mode."""

    SPRITE_2D = "2d"
    MESH_3D = "3d"


class SystemStatus(StrEnum):
    """Overall system health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # one subsystem in fallback
    SAFE_MODE = "safe_mode"  # multiple failures
    RECOVERING = "recovering"


# ------------------------------------------------------------------
# Base event
# ------------------------------------------------------------------


class ChimeraEvent(BaseModel):
    """Base class for all events on the Chimera Event Bus.

    Every event carries a unique ID, a UTC timestamp, and an optional
    correlation_id for tracing multi-step interactions (e.g. STT → LLM → TTS).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="UTC timestamp when the event was created.",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Links related events in a multi-step pipeline (e.g. a full STT→LLM→TTS cycle).",
    )


# ------------------------------------------------------------------
# Brain → Bridge events
# ------------------------------------------------------------------


class ActionIntent(ChimeraEvent):
    """Emitted by the Brain when the companion should perform a visible action.

    The Bridge translates this into a RenderCommand per the active renderer.
    """

    action: ActionKind = Field(description="Abstract action to perform.")
    emotion: Emotion = Field(default=Emotion.NEUTRAL, description="Emotion driving the action.")
    target: tuple[float, float] | None = Field(
        default=None, description="Target position in logical coordinates (0-1, 0-1)."
    )
    speech: str | None = Field(
        default=None, description="Optional speech text to accompany the action."
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Priority: 0=immediate (interrupt current), 10=background (queue).",
    )


class MoodChange(ChimeraEvent):
    """Emitted when the companion's emotional state transitions.

    The Body uses this to blend between emotional poses/morphs over
    a configurable transition duration.
    """

    previous: Emotion = Field(description="Previous emotional state.")
    current: Emotion = Field(description="New emotional state.")
    intensity: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Intensity of the emotion (0=subtle, 1=extreme)."
    )
    transition_ms: int = Field(
        default=500, ge=0, description="Duration of the blend transition in milliseconds."
    )
    cause: str | None = Field(
        default=None, description="Human-readable reason for the mood change (for telemetry)."
    )


class SpeakRequest(ChimeraEvent):
    """Emitted when the companion should vocalize text.

    The Bridge routes this to the active TTS engine.
    """

    text: str = Field(description="Text to speak.")
    interrupt: bool = Field(
        default=False,
        description="If True, stop current speech and immediately speak this text.",
    )
    emotion: Emotion = Field(
        default=Emotion.NEUTRAL, description="Emotion to apply as a vocal style hint."
    )


class ScreenGaze(ChimeraEvent):
    """Emitted when the Brain wants the companion to look at a screen region.

    Used for the 'follow active window' and 'gaze at cursor' features.
    """

    x: float = Field(description="Normalized X coordinate (0-1).")
    y: float = Field(description="Normalized Y coordinate (0-1).")
    duration_ms: int = Field(
        default=1500, description="How long to hold the gaze in milliseconds."
    )


# ------------------------------------------------------------------
# Bridge → Body events (RenderCommands)
# ------------------------------------------------------------------


class RenderContext(BaseModel):
    """Context passed to renderers during initialization."""

    model_config = ConfigDict(frozen=True)

    character_id: str = Field(default="default")
    dpi_scale: float = Field(default=1.0, description="Device pixel ratio.")
    screen_width: int = Field(default=1920)
    screen_height: int = Field(default=1080)
    debug_mode: bool = Field(default=False)


class MoodState(BaseModel):
    """Snapshot of current mood passed to renderers for visual blending."""

    model_config = ConfigDict(frozen=True)

    emotion: Emotion
    intensity: float = 1.0
    previous_emotion: Emotion | None = None
    transition_progress: float = Field(
        default=1.0, ge=0.0, le=1.0, description="0=start of blend, 1=complete."
    )


class RenderCommand(ChimeraEvent):
    """Concrete rendering instruction dispatched by the Bridge to the active renderer.

    This is the translation of an ActionIntent into renderer-specific terms.
    """

    animation: str = Field(
        default="idle", description="Animation clip or sprite sequence name."
    )
    morph_targets: dict[str, float] = Field(
        default_factory=dict,
        description="Morph target name → weight (0.0–1.0). Used in 3D for facial expressions.",
    )
    position: tuple[float, float] | None = Field(
        default=None, description="Target position in logical coords."
    )
    loops: int = Field(default=1, ge=0, description="Loop count; 0 = loop forever.")
    duration_ms: int = Field(default=1000, description="Animation duration in ms.")
    blend_ms: int = Field(
        default=200, description="Cross-blend duration for smooth transitions."
    )


# ------------------------------------------------------------------
# Body → Bridge events (Input Events)
# ------------------------------------------------------------------


class InputEvent(ChimeraEvent):
    """Base for user input events captured by the Body and forwarded to the Brain."""

    source: Literal["keyboard", "mouse", "drag_drop", "voice", "system"] = Field(
        description="Origin of the input event."
    )


class TextInputEvent(InputEvent):
    """Text typed by the user in the chat dock."""

    text: str
    source: Literal["keyboard", "voice"] = "keyboard"  # type: ignore[assignment]


class VoiceInputEvent(InputEvent):
    """Transcribed voice input from STT pipeline."""

    text: str
    source: Literal["keyboard", "voice"] = "voice"  # type: ignore[assignment]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    language: str | None = None


class MouseHoverEvent(InputEvent):
    """Mouse position update (throttled by the Bridge)."""

    x: float
    y: float
    window_title: str | None = None
    source: Literal["keyboard", "mouse", "drag_drop", "voice", "system"] = "mouse"  # type: ignore[assignment]


class FileDropEvent(InputEvent):
    """File(s) dropped onto the companion overlay."""

    file_paths: list[str]
    window_title: str | None = None
    source: Literal["keyboard", "mouse", "drag_drop", "voice", "system"] = "drag_drop"  # type: ignore[assignment]


class HotkeyEvent(InputEvent):
    """Global hotkey triggered (e.g. push-to-talk)."""

    hotkey: str
    pressed: bool = True
    source: Literal["keyboard", "mouse", "drag_drop", "voice", "system"] = "keyboard"  # type: ignore[assignment]


class WindowFocusEvent(InputEvent):
    """Active window changed. Used for screen-awareness context."""

    window_title: str
    process_name: str | None = None
    source: Literal["keyboard", "mouse", "drag_drop", "voice", "system"] = "system"  # type: ignore[assignment]


# ------------------------------------------------------------------
# System / lifecycle events
# ------------------------------------------------------------------


class SystemEvent(ChimeraEvent):
    """Base for lifecycle and infrastructure events."""


class RendererSwapRequest(SystemEvent):
    """Request a hot-swap to a different renderer mode."""

    target: RendererMode


class RendererSwapComplete(SystemEvent):
    """Notification that a hot-swap completed successfully."""

    from_mode: RendererMode
    to_mode: RendererMode
    duration_ms: int


class SafeModeEntered(SystemEvent):
    """Safe Mode was activated due to multiple subsystem failures."""

    failed_subsystems: list[str]
    reason: str


class SafeModeExited(SystemEvent):
    """Safe Mode was exited after successful recovery."""

    recovered_subsystems: list[str]


class Heartbeat(SystemEvent):
    """Periodic heartbeat emitted by each layer for watchdog monitoring."""

    layer: Literal["brain", "bridge", "body"]
    pid: int
    uptime_s: float


class ShutdownRequest(SystemEvent):
    """Graceful shutdown requested."""

    reason: str = "user_initiated"


class TelemetryEvent(ChimeraEvent):
    """Structured log event captured by the Telemetry ring buffer."""

    severity: EventSeverity
    message: str
    module: str | None = None
    exception_type: str | None = None
    exception_traceback: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ContextUpdate(ChimeraEvent):
    """Bridge → Brain: updated environmental context (throttled to 10 Hz)."""

    active_window_title: str | None = None
    mouse_position: tuple[float, float] | None = None
    dropped_files: list[str] | None = None
    system_status: SystemStatus = SystemStatus.HEALTHY


# ------------------------------------------------------------------
# Union type for subscription type-checking
# ------------------------------------------------------------------

# All event types that can flow through the EventBus.
AnyEvent = (
    ActionIntent
    | MoodChange
    | SpeakRequest
    | ScreenGaze
    | RenderCommand
    | InputEvent
    | TextInputEvent
    | VoiceInputEvent
    | MouseHoverEvent
    | FileDropEvent
    | HotkeyEvent
    | WindowFocusEvent
    | SystemEvent
    | RendererSwapRequest
    | RendererSwapComplete
    | SafeModeEntered
    | SafeModeExited
    | Heartbeat
    | ShutdownRequest
    | TelemetryEvent
    | ContextUpdate
)