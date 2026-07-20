"""Abstract Renderer Protocol — the contract every renderer must satisfy.

The Bridge never knows which concrete renderer is active. It only depends on
this Protocol. Adding a new renderer (e.g. VR, Raycast, Remote) requires only
that it passes the conformance suite in tests/conformance/.

Author: Project Chimera Engineering Team
Version: 1.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from chimera.bridge.events import MoodState, RenderCommand, RenderContext


@runtime_checkable
class AbstractRenderer(Protocol):
    """Protocol contract for all Chimera renderers.

    Renderers live in the Body layer and receive commands exclusively
    through the Bridge. They must never import from Brain.
    """

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> Literal["2d", "3d"]:
        """Unique identifier for this renderer's mode.

        Returns:
            "2d" for sprite-based, "3d" for mesh-based renderers.
        """
        ...

    @property
    def is_ready(self) -> bool:
        """Whether the renderer has been initialized and can accept commands.

        The Bridge checks this before dispatching RenderCommands.
        """
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self, ctx: RenderContext) -> None:
        """One-time setup: create GPU context, load default assets, warm caches.

        Called by the RendererRegistry after instantiation and on every hot-swap
        into this renderer. Must be idempotent — if already initialized, return
        immediately without side effects.

        Args:
            ctx: RenderContext carrying the character ID, display DPI, and
                 any bridge-supplied hints.

        Raises:
            RendererInitError: If initialization fails after internal retries.
        """
        ...

    async def teardown(self) -> None:
        """Gracefully release resources: GPU context, textures, animations.

        Called before hot-swapping to a different renderer and on application
        shutdown. Must complete within 3 seconds; the Bridge will force-kill
        the widget if it times out.

        After teardown, is_ready must return False until initialize is called
        again.
        """
        ...

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    async def apply(self, cmd: RenderCommand) -> None:
        """Apply a RenderCommand dispatched by the Bridge.

        This is the primary entry point for all visual updates. The Bridge
        translates abstract ActionIntents into concrete RenderCommands via
        the per-renderer adapter.

        Args:
            cmd: A typed RenderCommand (play animation, change morph target,
                 update sprite frame, etc.).
        """
        ...

    async def on_mood_change(self, mood: MoodState) -> None:
        """React to a MoodState change from the Brain.

        Mood changes are separate from RenderCommands because they may
        trigger multi-frame transitions (e.g. blending from happy to sad
        over 500ms) rather than discrete frame swaps.

        Args:
            mood: The new mood state with optional intensity and transition hints.
        """
        ...

    # ------------------------------------------------------------------
    # Asset management
    # ------------------------------------------------------------------

    async def load_character(self, character_id: str) -> bool:
        """Load a character's full asset set (sprites or model + animations).

        Called after initialize() and when the user selects a different
        character in Settings. Must handle missing assets gracefully by
        falling back to the default character.

        Args:
            character_id: The character key matching assets/<character>/manifest.yaml.

        Returns:
            True if the character loaded successfully, False if fallback was used.
        """
        ...

    async def load_asset(self, asset_id: str) -> bool:
        """Load a single asset on demand (e.g. a special animation triggered
        by a plugin).

        Args:
            asset_id: An asset path relative to the character's asset directory.

        Returns:
            True if loaded, False if not found (caller should handle gracefully).
        """
        ...

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def snapshot(self) -> bytes:
        """Capture the current render output as a PNG byte string.

        Used for thumbnail generation in the character library and for
        debug/diagnostic snapshots. Must not block the render loop.

        Returns:
            PNG-encoded image bytes.
        """
        ...

    # ------------------------------------------------------------------
    # Qt Integration
    # ------------------------------------------------------------------

    def widget(self) -> QWidget:
        """Return the Qt widget that hosts this renderer's output.

        The widget is reparented by the Bridge during hot-swap. It must be
        a valid QWidget subclass (QGraphicsView for 2D, QOpenGLWidget for 3D).

        Returns:
            The renderer's top-level widget.
        """
        ...

    def widget_native_id(self) -> int:
        """Return the native window handle (winId) for the renderer widget.

        Used by the watchdog and input hooks to associate OS-level events
        with the correct renderer instance.

        Returns:
            The platform-native window ID as an integer.
        """
        ...


# ------------------------------------------------------------------
# Exception hierarchy
# ------------------------------------------------------------------


class RendererError(Exception):
    """Base class for all renderer-related errors."""


class RendererInitError(RendererError):
    """Raised when a renderer fails to initialize after exhausting retries."""


class RendererCommandError(RendererError):
    """Raised when a renderer cannot process a RenderCommand.

    The command text is included for telemetry. This is always non-fatal;
    the Bridge logs it and continues.
    """

    def __init__(self, command: str, reason: str) -> None:
        self.command = command
        self.reason = reason
        super().__init__(f"Failed to apply '{command}': {reason}")


class AssetNotFoundError(RendererError):
    """Raised when a requested asset cannot be located or loaded."""


class RendererTeardownTimeoutError(RendererError):
    """Raised by the Bridge when a renderer's teardown() exceeds the 3s limit."""