# PROJECT CHIMERA — MASTER TECHNICAL SPECIFICATION DOCUMENT
**Version:** 1.0 | **Classification:** Internal — Engineering Blueprint
**Author:** Office of the CTO / Lead Architect
**Status:** Approved for Sprint 1 Initiation

---

## PREAMBLE — ENGINEERING MANDATE

Project Chimera is the consumer-grade synthesis of two antecedent systems:
- **Brain donor:** `kinj-code/bubby` — autonomy, behavior tree, memory, interaction loop.
- **Heart donor:** `rayenfeng/riko_project` — conversational pipeline (LLM + Whisper + TTS) and 3D gesture/emotion sync.

The previous prototype shipped with terminal-only configuration, fragile input handling, monolithic UI/logic coupling, and no formal recovery story. Chimera is a **clean-room redevelopment** that discards that debt while preserving validated logic. The non-negotiable constraints are: GUI-first configuration, renderer-agnostic modularity, asynchronous non-blocking UI, and 99.9% overlay uptime.

This document is the canonical reference. Where any other artifact conflicts with this spec, **this document wins.**

---

## SECTION 1 — SYSTEM ARCHITECTURE BLUEPRINT: "BRAIN → BRIDGE → BODY"

### 1.1 Topology Overview

Chimera is partitioned into three strictly decoupled layers connected by a single typed asynchronous event bus. No layer may import from a non-adjacent layer.

```
┌──────────────────────────────────────────────────────────────────┐
│                         BRAIN (Cognitive Core)                    │
│  LLM Orchestrator · Behavior Tree · Memory · Perception · Intent │
└───────────────────────────────┬──────────────────────────────────┘
                                │  emits: ActionIntent, MoodChange,
                                │         SpeakRequest, ScreenGaze
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                        BRIDGE (Middleware)                        │
│  Event Bus · State Manager · Renderer Registry · Vault ·         │
│  Telemetry · Scheduler · Watchdog                                │
└───────────────────────────────┬──────────────────────────────────┘
                                │  routes: RenderCommand, AudioCommand,
                                │         InputEvent, SystemEvent
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                          BODY (Presentation)                      │
│  AbstractRenderer ← [Sprite2D | Mesh3D] · Audio I/O · Input Hooks│
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 The Brain (Cognitive Core)

The Brain is **pure Python, headless, and renderer-blind.** It must be unit-testable without a display server.

**Sub-modules:**
- **LLM Orchestrator** — manages a fallback chain (Local `llama.cpp` → Cloud provider → Cached/Offline persona). Exposes a single `async generate(prompt, ctx) -> AsyncIterator[str]` streaming interface.
- **Behavior Tree** — ported from Bubby but refactored onto `py_trees` or a custom async variant. Drives idle loops, reactive gestures, and scheduled "ping" behaviors.
- **Memory System** — three tiers:
  - *Short-term:* rolling last-N turns (in-RAM deque).
  - *Episodic:* per-session summaries persisted to SQLite via `sqlite-utils`.
  - *Long-term:* vector-indexed summaries (FAISS or `chromadb` local) keyed by user.
- **Perception Module** — receives `InputEvent`s from the Bridge (mouse coords, active window title, drag-dropped files) and translates them into semantic context ("user is coding", "user dropped a PDF").
- **Intent Parser** — converts LLM output into structured `ActionIntent` Pydantic objects. Uses grammar-constrained decoding where possible to prevent hallucinated actions.

### 1.3 The Bridge (Middleware / Event Bus)

The Bridge is the **single source of truth** for cross-layer communication. It is the only layer permitted to hold shared mutable state.

**Core components:**

| Component | Responsibility |
|---|---|
| **Event Bus** | Async pub/sub with typed Pydantic event schemas. Built on `asyncio.Queue` per subscriber; integrated with Qt via `qasync`. |
| **State Manager** | Holds canonical application state. Persists atomically (tmp-file + `os.replace`). Crash-safe. |
| **Renderer Registry** | Tracks active renderer. Performs hot-swap between 2D/3D without restarting the Brain. |
| **Credential Vault** | Wraps `keyring` for OS-native secret storage. API keys never touch disk in plaintext. |
| **Telemetry** | Ring-buffered structured logger (`loguru`). Last 10,000 events retained for post-mortem. |
| **Scheduler** | Cron-like async scheduler for periodic tasks (memory compaction, model warm-up). |
| **Watchdog** | Heartbeat monitor. If a layer fails to pulse within 5s, Bridge triggers Safe Mode. |

**Event schema example (Pydantic v2):**

```python
class ActionIntent(BaseModel):
    action: Literal["wave","point","idle","move_to","gaze_at","emote"]
    emotion: Literal["neutral","happy","sad","curious","annoyed","thinking"]
    target: tuple[float, float] | None = None
    speech: str | None = None
    priority: int = 0  # 0=immediate, 10=background
```

### 1.4 The Body (Presentation Layer)

The Body is **pluggable.** It implements a `Protocol` defined in `body/renderers/abstract.py`. The Bridge never knows which renderer is active; it only knows the interface.

**Abstract Renderer Protocol (mandatory contract):**

```python
class AbstractRenderer(Protocol):
    async def on_render_command(self, cmd: RenderCommand) -> None: ...
    async def on_mood_change(self, mood: MoodState) -> None: ...
    async def load_asset(self, asset_id: str) -> bool: ...
    async def teardown(self) -> None: ...
    def widget(self) -> QWidget: ...  # returns Qt widget for embedding
```

**Concrete implementations:**
- `Sprite2DRenderer` — `QGraphicsScene` + sprite sheet atlas + skeletal frame blending.
- `Mesh3DRenderer` — `QOpenGLWidget` + ModernGL context + glTF loader (via `pygltflib`).

**Hot-swap protocol:**
1. User clicks "Switch to 3D" in Settings.
2. Bridge emits `RendererSwapRequest`.
3. Active renderer's `teardown()` is awaited (max 3s timeout, then forced).
4. Bridge updates `State.active_renderer = "3D"`.
5. Registry instantiates `Mesh3DRenderer`, calls `load_asset(current_character)`.
6. Brain is **never** notified. It continues emitting intents; Bridge simply routes them to the new consumer.

### 1.5 Communication Pattern

- **Brain → Bridge:** `publish(ActionIntent(...))`
- **Bridge → Body:** `dispatch(RenderCommand(...))` (translated from ActionIntent by a per-renderer adapter)
- **Body → Bridge:** `publish(InputEvent(...))` (mouse, keyboard, drag-drop)
- **Bridge → Brain:** `dispatch(ContextUpdate(...))` (throttled to 10 Hz max)

This unidirectional flow prevents the classic "spaghetti callback" antipattern and makes every interaction replayable for debugging.

---

## SECTION 2 — TECHNOLOGICAL STACK RECOMMENDATION (2026-GRADE)

### 2.1 Definitive Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.12+ | Ecosystem maturity, AI stack alignment. |
| **GUI Framework** | PySide6 (Qt 6.7+) | Industry standard, native OpenGL widgets, mature signal/slot. |
| **Async Bridge** | `qasync` | Bridges `asyncio` with Qt event loop — **critical** for non-blocking UI. |
| **2D Rendering** | `QGraphicsScene` + `QPainter` | Native Qt, zero additional deps, hardware-accelerated. |
| **3D Rendering** | ModernGL + `QOpenGLWidget` | Lightweight OpenGL wrapper; no game-engine bloat. |
| **3D Asset Format** | glTF 2.0 (`pygltflib`) | Industry standard, animation-ready. |
| **Local LLM** | `llama-cpp-python` (CPU/CUDA/Metal builds) | Best-in-class local inference; GGUF quantization. |
| **Cloud LLM** | `openai`, `anthropic` SDKs | Provider abstraction via internal `LLMProvider` interface. |
| **STT** | `faster-whisper` | 4× faster than openai-whisper, CTranslate2 backend. |
| **TTS** | Piper | Local-first, real-time, multi-voice. |
| **Global Input** | `pynput` | Cross-platform mouse/keyboard hooks. |
| **Screen Awareness** | `mss` (capture) + `pygetwindow` / `pywinctl` | Window enumeration + screenshot for vision pipeline. |
| **Memory** | SQLite (`sqlite-utils`) + FAISS local | Zero-config persistence + on-device semantic recall. |
| **State Models** | Pydantic v2 | Typed validation, JSON schema generation, fast. |
| **Secrets** | `keyring` | OS keychain (Credential Manager / Keychain / SecretService). |
| **Logging** | `loguru` | Structured, rotation, sinks for file + UI. |
| **Packaging** | `PyInstaller` + `briefcase` (eval) | Single-file distributable; briefcase for native installers. |
| **Package Mgmt** | `uv` | 10–100× faster than pip; lockfile-first. |
| **CI/CD** | GitHub Actions | Smoke tests on every push; signed builds on tag. |
| **Testing** | `pytest` + `pytest-asyncio` + `pytest-qt` | Async + Qt widget testing in one harness. |

### 2.2 Prohibited Dependencies

- ❌ **No monolithic game engines** (Unity, Godot, Unreal). They violate the "renderer-agnostic" mandate and balloon binary size.
- ❌ **No global pip installs.** Everything lives in `uv` virtual envs pinned by `pyproject.toml`.
- ❌ **No synchronous network calls** anywhere in the Brain or Body. All I/O must be `async`.

### 2.3 Dependency Hygiene

Because Chimera inherits from two upstream codebases (Bubby + Riko patterns), dependency conflicts are guaranteed. Mitigation:

1. A single `pyproject.toml` with **strict upper bounds** on AI libraries (torch, transformers) to avoid CUDA breakage.
2. A `uv.lock` committed to the repo.
3. A `pip check` step in CI to detect transitive conflicts.
4. CPU-only `torch` build by default; CUDA/Metal variants installed via optional `[extra]` groups.

---

## SECTION 3 — THE "CHIMERA" MODULE DEFINITION

### 3.1 Repository Structure

```
chimera/
├── pyproject.toml
├── uv.lock
├── CREDITS.md
├── REFERENCES.md
├── README.md
├── LICENSE
├── .github/workflows/         # CI/CD
├── config/
│   ├── default.yaml
│   └── profiles/
│       ├── basic.yaml
│       ├── balanced.yaml
│       └── advanced.yaml
├── assets/
│   ├── sprites/<character>/
│   ├── models/<character>/
│   └── voices/
├── docs/
│   ├── architecture.md
│   ├── api/                   # auto-generated
│   └── troubleshooting.md
├── src/chimera/
│   ├── __init__.py
│   ├── main.py                # entrypoint, watchdog-aware
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── orchestrator.py    # LLM fallback chain
│   │   ├── providers/
│   │   │   ├── local.py       # llama.cpp
│   │   │   ├── cloud.py       # OpenAI/Anthropic
│   │   │   └── offline.py     # cached persona fallback
│   │   ├── behavior/
│   │   │   ├── tree.py
│   │   │   ├── nodes.py
│   │   │   └── states.py
│   │   ├── memory/
│   │   │   ├── short_term.py
│   │   │   ├── episodic.py
│   │   │   └── long_term.py
│   │   └── perception/
│   │       ├── screen.py
│   │       └── intent_parser.py
│   ├── bridge/
│   │   ├── __init__.py
│   │   ├── bus.py             # EventBus
│   │   ├── events.py          # Pydantic event schemas
│   │   ├── state.py           # StateManager (atomic writes)
│   │   ├── registry.py        # RendererRegistry
│   │   ├── vault.py           # CredentialVault (keyring)
│   │   ├── telemetry.py
│   │   ├── scheduler.py
│   │   └── watchdog.py
│   ├── body/
│   │   ├── __init__.py
│   │   ├── renderers/
│   │   │   ├── abstract.py    # Protocol
│   │   │   ├── sprite2d.py
│   │   │   └── mesh3d.py
│   │   ├── audio/
│   │   │   ├── tts.py         # Piper wrapper
│   │   │   ├── stt.py         # faster-whisper wrapper
│   │   │   └── stream.py      # audio I/O
│   │   └── input/
│   │       ├── global_hooks.py  # pynput
│   │       └── drag_drop.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── companion_overlay.py  # the transparent always-on-top window
│       ├── chat_dock.py
│       ├── settings/
│       │   ├── settings_dialog.py
│       │   ├── general_tab.py
│       │   ├── ai_tab.py
│       │   ├── visuals_tab.py
│       │   ├── voice_tab.py
│       │   └── profiles_tab.py
│       ├── wizards/
│       │   └── first_run.py    # hardware spec-check
│       └── widgets/
│           ├── tooltip.py      # contextual help
│           └── toast.py        # non-blocking notifications
└── tests/
    ├── unit/
    ├── integration/
    └── smoke/
```

### 3.2 The Modular Rendering Engine — Detailed Design

The hot-swap capability is the project's signature feature. Implementation:

**Step 1 — Abstract Interface (`body/renderers/abstract.py`):**
```python
class AbstractRenderer(Protocol):
    @property
    def mode(self) -> Literal["2d", "3d"]: ...
    async def initialize(self, ctx: RenderContext) -> None: ...
    async def apply(self, cmd: RenderCommand) -> None: ...
    async def load_character(self, char_id: str) -> None: ...
    async def snapshot(self) -> bytes: ...  # for thumbnails / transitions
    async def teardown(self) -> None: ...
    def widget(self) -> QWidget: ...
```

**Step 2 — Adapter Pattern in the Bridge:**
The Brain emits `ActionIntent(action="wave", emotion="happy")`. The Bridge's `RendererAdapter` translates this:
- If `mode == "2d"` → `RenderCommand(sprite="wave_happy", loops=1)`
- If `mode == "3d"` → `RenderCommand(anim_clip="Wave", morph_targets={"smile": 1.0})`

**Step 3 — Hot-Swap Sequence:**
1. User toggles in Settings → `VisualsTab`.
2. UI publishes `RendererSwapRequest(target="3d")`.
3. Bridge acquires `swap_lock` (prevents concurrent swaps).
4. Bridge calls `current.teardown()` with a 3s timeout; on timeout, force-releases GPU context.
5. Bridge instantiates new renderer, calls `initialize()` and `load_character(state.current_character)`.
6. Bridge swaps the Qt widget parent in one atomic operation (off-screen render → reparent → show).
7. A `RendererSwapComplete` event is published; UI shows a brief "Applied" toast.
8. The Brain's behavior tree continues uninterrupted — **zero downtime for cognition.**

**Step 4 — Shared Asset Cache:**
Both renderers draw from `assets/<character>/manifest.yaml`. The manifest declares parallel assets:
```yaml
character: "Aria"
sprites: { idle: "idle.png", wave: "wave.png", ... }
model: "aria.glb"
animations: { wave: "Wave.fbx", idle: "Idle.fbx" }
morph_targets: { smile: "Mouth_Smile", ... }
```
This guarantees a character is portable across both engines.

---

## SECTION 4 — ERROR HANDLING & STABILITY MANIFESTO

### 4.1 Principles

1. **No silent failures.** Every caught exception emits a `TelemetryEvent` with severity.
2. **No UI freeze.** Any operation exceeding 100ms must run off the Qt event loop.
3. **Degradation, not termination.** The companion degrades to a "Safe Persona" rather than crashing.
4. **Recoverability.** State is persisted atomically; the app can resume mid-conversation after a crash.

### 4.2 Failure Modes & Protocols

| Failure | Detection | Response |
|---|---|---|
| **LLM load timeout (>30s)** | Watchdog heartbeat | 1. Kill load process. 2. Try smaller quant (Q4 → Q3). 3. Fall back to cloud provider (if API key configured). 4. Fall back to `OfflinePersona` (pre-scripted responses). 5. Notify user via toast. |
| **LLM generation hang (>60s)** | Per-call asyncio timeout | Cancel generation; emit `MoodChange(thinking→apologetic)`; respond with cached apology. |
| **GPU context loss (3D)** | ModernGL `GLContextError` | 1. Freeze 3D widget. 2. Auto-reinit context (max 2 retries). 3. On persistent failure, auto-fallback to 2D renderer + user toast. |
| **Whisper STT failure** | Exception in audio pipeline | Disable voice input; switch UI to text-only; auto-retry STT every 60s. |
| **Piper TTS failure** | Exception | Stream audio via OS-native TTS (`pyttsx3`) as fallback; queue audio in Bridge. |
| **API timeout (cloud LLM)** | 10s connect / 30s read | Exponential backoff (1s, 2s, 4s, 8s, max 3 retries); queue subsequent user messages. |
| **State file corruption** | Pydantic validation error on load | 1. Restore from `.bak`. 2. If `.bak` fails, load `default.yaml`. 3. Preserve user's `memories.db` (never overwrite episodic memory). |
| **Renderer crash** | Process signal | Bridge detects lost widget; hot-swaps to 2D; logs crash dump. |
| **Memory exhaustion** | `psutil` threshold (>85% RAM) | 1. Evict short-term memory. 2. Compact FAISS index. 3. Unload cloud SDKs. 4. If still high, restart Brain in headless mode (visuals continue). |
| **Drag-drop of unsupported file** | Parser exception | Toast: "I can't read that format yet" + log file type for future support. |
| **Network outage** | Connectivity probe | Switch to `OfflinePersona`; queue cloud-bound intents; auto-resume on reconnect. |

### 4.3 Safe Mode

When three or more subsystems fail within 60s, Bridge enters **Safe Mode:**
- 2D renderer forced (lowest resource).
- LLM forced to `OfflinePersona`.
- Audio forced to OS TTS.
- Banner shown: "Chimera is running in Safe Mode. Click to diagnose."
- Diagnostic panel lists failed subsystems with one-click "Retry."

### 4.4 The Watchdog Process

A separate lightweight process (`chimera_watchdog`) runs alongside the main app:
- Heartbeats every 2s via named pipe / Unix socket.
- If main app misses 3 heartbeats (6s), watchdog:
  1. Captures stack trace via `faulthandler` dump.
  2. Notifies OS notification center.
  3. Offers to relaunch.

### 4.5 Telemetry "Black Box"

`Telemetry` keeps a ring buffer of the last 10,000 events in memory and the last 1,000 on disk (`logs/blackbox.jsonl`). On any unhandled exception, the entire buffer is flushed. Users can click "Send Diagnostics" in Settings to package it (PII-scrubbed via regex) into a zip for support.

---

## SECTION 5 — DEVELOPMENT ROADMAP (SPRINT PLAN)

### Sprint 0 — Foundation (Week 1)
**Deliverables:**
- Repo initialized; `pyproject.toml`, `uv.lock`, `CREDITS.md`, `REFERENCES.md` committed.
- CI pipeline (lint `ruff`, typecheck `mypy --strict`, smoke test "app launches").
- Pre-commit hooks.
- Directory skeleton from Section 3.1.

**Exit Criteria:** `uv run chimera --version` prints version; CI green on `main`.

### Sprint 1 — The Shell (Weeks 2–3)
**Deliverables:**
- `MainWindow` with menu bar, system tray, and a transparent `CompanionOverlay`.
- `qasync` event loop wired in.
- `EventBus` MVP (publish/subscribe with Pydantic events).
- `StateManager` with atomic writes.
- First-run hardware spec wizard (CPU cores, RAM, GPU detection via `psutil` + `GPUtil`).

**Exit Criteria:** App launches, shows overlay, persists window position across restarts, hardware profile generated.

### Sprint 2 — The Bridge (Weeks 4–5)
**Deliverables:**
- Full event schema in `bridge/events.py`.
- `RendererRegistry` with hot-swap protocol (tested with two stub renderers).
- `CredentialVault` (keyring integration).
- `Watchdog` subprocess + heartbeat.
- `Telemetry` ring buffer + loguru sinks.

**Exit Criteria:** A "Hello World" Brain stub publishes `ActionIntent("wave")`; Bridge routes it to two stub renderers; swap works without restart; telemetry captures the swap.

### Sprint 3 — The Brain (Weeks 6–8)
**Deliverables:**
- Port Bubby's behavior tree to async; refactor onto `py_trees` or equivalent.
- `LLMProvider` interface; `LocalProvider` (llama.cpp); `CloudProvider` (OpenAI/Anthropic).
- Fallback chain in `orchestrator.py`.
- Memory tiers (short-term + episodic SQLite).
- `IntentParser` with grammar-constrained decoding for actions.
- Unit tests for every Brain module (≥80% coverage).

**Exit Criteria:** Brain runs headless; responds to text input via console test harness; persists conversation to SQLite; falls back gracefully when local LLM unavailable.

### Sprint 4 — The Body: 2D (Weeks 9–10)
**Deliverables:**
- `AbstractRenderer` Protocol finalized.
- `Sprite2DRenderer` with sprite atlas loading, frame animation, mood blending.
- CompanionOverlay renders 2D sprites; responds to `RenderCommand`s.
- Drag-drop support for images/text files.

**Exit Criteria:** User can chat with companion; sprite animates moods; files dropped onto companion trigger perception events.

### Sprint 5 — The Body: 3D (Weeks 11–13)
**Deliverables:**
- `Mesh3DRenderer` using ModernGL + `QOpenGLWidget`.
- glTF loader; animation playback; morph targets for facial expressions.
- Hot-swap from 2D ↔ 3D verified end-to-end.
- GPU crash recovery protocol implemented.

**Exit Criteria:** Toggle 2D/3D in Settings works without restart; 3D model animates emotions; GPU context loss auto-recovers.

### Sprint 6 — Audio Pipeline (Weeks 14–15)
**Deliverables:**
- Piper TTS wrapper; faster-whisper STT wrapper.
- Push-to-talk hotkey (via `pynput`); ambient VAD optional.
- Voice activity indicator in overlay.
- Audio device selection in Settings.

**Exit Criteria:** User speaks → companion transcribes → LLM responds → companion speaks. End-to-end latency < 2.5s on reference hardware.

### Sprint 7 — UI & Settings (Weeks 16–17)
**Deliverables:**
- Full Settings dialog: General, AI, Visuals, Voice, Profiles, Diagnostics.
- Contextual tooltips on every setting.
- Profile presets (Basic / Balanced / Advanced).
- Character library tab (select, import, download).
- Toast notification system.

**Exit Criteria:** Every config knob exposed via GUI; no `.json` editing required; non-technical user can fully configure the app.

### Sprint 8 — Polish & Hardening (Weeks 18–20)
**Deliverables:**
- Safe Mode UI; diagnostic panel.
- Watchdog subprocess integration.
- Memory compaction scheduler.
- Packaging: Windows `.msi`, macOS `.dmg`, Linux `.AppImage`.
- Closed beta with ≤10 testers; telemetry-driven bug triage.

**Exit Criteria:** 99.9% overlay uptime over 24-hour soak test; zero crashes on 5 reference machines; beta release tagged.

---

## SECTION 6 — EXPERT ENHANCEMENTS (BLIND-SPOT ANALYSIS)

After 50 years of collective engineering scar tissue, these are the failure modes the current plan does not yet defend against — and the prescriptions for each.

### 6.1 Latency: The "Dead Air" Problem

**Blind spot:** The naive chain `STT → LLM → TTS` can produce 3–5 seconds of silence. Users perceive this as "broken."

**Expert Solution:**
- **Streaming everywhere.** LLM must yield tokens via `AsyncIterator`. Piper supports streaming synthesis; begin TTS on the first sentence boundary (≈200ms after first token), not on full response.
- **Filler animations.** The Brain emits `MoodChange("thinking")` the instant LLM is invoked; the renderer plays a fidget/look-around animation that masks the wait.
- **Predictive prefetch.** While user is mid-sentence (VAD still active), begin speculative LLM prefill with a soft prompt. Discard if final transcript diverges.
- **Latency budget.** Define SLOs: STT < 300ms, first LLM token < 500ms, first audio < 1.2s. Telemetry flags violations.

### 6.2 UI Freeze During LLM Load

**Blind spot:** `llama.cpp` model load (especially 7B+) can block 10–30s. Even in a thread, GIL contention with Qt can stutter the UI.

**Expert Solution:**
- Load the model in a **separate process** (`multiprocessing.Process`), communicate via `asyncio.Queue` over a pipe. This bypasses the GIL entirely.
- Show a determinate progress bar in the overlay ("Waking up… 42%") driven by `llama.cpp`'s load-progress callback.
- Keep a small "always-loaded" 1B model warm for instant responses while the larger model loads.

### 6.3 The "Two Apps" Trap

**Blind spot:** Building 2D and 3D as parallel codepaths eventually causes logic drift (2D gets a feature, 3D doesn't).

**Expert Solution:**
- A **single behavior vocabulary** defined in `bridge/events.py`. Both renderers must implement the full vocabulary; missing implementations raise `NotImplementedError` at startup (fail-fast).
- A **renderer conformance test suite** (`tests/conformance/test_renderer_protocol.py`) that any new renderer must pass. CI runs it against both renderers on every push.

### 6.4 Character Logic Future-Proofing

**Blind spot:** Hard-coding emotion → animation mappings will rot as characters are added.

**Expert Solution:**
- Each character ships a `persona.yaml` declaring its emotional vocabulary and asset mapping. The Brain emits **abstract emotions** (`happy`); the persona translates to **concrete assets** (`aria_happy.fbx` vs `bob_smile.png`).
- This means third-party character creators can ship compatible packs without touching Brain code.

### 6.5 Privacy & Screen Awareness

**Blind spot:** "Screen awareness" can capture passwords, DMs, banking pages. A single leaked screenshot is a PR catastrophe.

**Expert Solution:**
- **On-device only.** Vision pipeline never transmits pixels. All processing local.
- **Redaction filter.** A configurable blocklist of window-title keywords (`*password*`, `*bank*`, `*1password*`) — when active, vision is suppressed.
- **Explicit opt-in.** Screen awareness defaults OFF. First-enable shows a consent dialog explaining what is and isn't captured.
- **Audit log.** Every screen capture is logged locally; user can review in Settings → Privacy.

### 6.6 Multi-Monitor & HiDPI

**Blind spot:** Companions get lost on disconnect; sprites render at wrong size on 4K.

**Expert Solution:**
- Persist companion position **per-monitor** (keyed by display serial).
- Listen to Qt's `QScreen` add/remove signals; auto-migrate companion to primary display if its screen vanishes.
- All rendering uses logical DPI units; ModernGL viewport scales via `devicePixelRatio`.

### 6.7 Battery & Thermal (Laptops)

**Blind spot:** A 7B LLM at full tilt will drain a MacBook in 40 minutes and spin fans to jet-engine levels.

**Expert Solution:**
- **Adaptive throttle.** Detect battery state (`psutil.sensors_battery()`); when unplugged, auto-downshift to 3B model and reduce idle behavior frequency.
- **User-presence detection.** If no input for 5 minutes, Brain enters "sleep" — unloads LLM, freezes behavior tree, sprite shows sleeping animation. Wake on keypress.
- **Thermal probe.** On macOS, read SMC; on Windows, WMI; if CPU > 90°C, throttle.

### 6.8 Conversational Continuity Across Sessions

**Blind spot:** Most companions reset every launch. Users hate reintroducing themselves.

**Expert Solution:**
- On graceful shutdown, Brain writes an episodic summary ("User was working on a Python PR; we discussed async patterns; user seemed tired").
- On next launch, summary is injected into the system prompt: *"Last time, you and the user were discussing X."*
- This is **the** feature that converts a gimmick into a companion. Prioritize it in Sprint 3.

### 6.9 The "Update Broke My Character" Problem

**Blind spot:** A new app version changes the persona schema; user's custom character stops loading.

**Expert Solution:**
- Persona files declare a `schema_version`. Brain runs a migrator on load (`migrate_persona_v1_to_v2`).
- Unknown fields are preserved, not dropped.
- A "Character Workshop" debug tab lets users validate their persona file against the current schema.

### 6.10 Plugin Architecture (Future-Proofing)

**Blind spot:** Tomorrow you'll want a VR renderer, a new LLM provider, a custom skill.

**Expert Solution:**
- Adopt Python **entry points** (`importlib.metadata.entry_points`). Renderers, LLM providers, and skills are all discoverable plugins.
- A `chimera.plugin` group registers concrete classes; Bridge loads them at startup.
- Third parties can ship `chimera-renderer-vr` as a pip package and it Just Works.

---

## CLOSING DIRECTIVE TO THE ENGINEERING TEAM

Project Chimera is not a feature list — it is an **architecture.** The features will change quarterly; the Brain-Bridge-Body topology must not. Build the interfaces first, the implementations second, the polish third. Every line of code you write this quarter should be answerable to the question: *"Could I replace this component without touching the others?"* If the answer is no, stop and refactor.

The benchmark is not Bubby. The benchmark is not Riko. The benchmark is the experience of a non-technical user, on a mid-range laptop, at 11 PM, who needs to feel that something on their screen gives a damn.

Build accordingly.

— **Office of the CTO, Project Chimera**
*Specification v1.0 — Approved for Sprint 0 kickoff.*