# Project Chimera

A modular, renderer-agnostic AI desktop companion. Brain → Bridge → Body.

## Quick Start

```bash
# Install uv (if not already installed)
pip install uv

# Clone and enter the project
git clone https://github.com/kinj-code/chimera.git
cd chimera

# Create a virtual environment and install dependencies
uv sync

# Run the app
uv run chimera

# Run with a specific profile
uv run chimera --profile advanced

# Print version
uv run chimera --version
```

## Architecture

Chimera is partitioned into three strictly decoupled layers:

```
BRAIN (Cognitive Core)
  LLM Orchestrator · Behavior Tree · Memory · Perception · Intent
        │
BRIDGE (Middleware)
  Event Bus · State Manager · Renderer Registry · Vault · Telemetry · Watchdog
        │
BODY (Presentation)
  AbstractRenderer ← [Sprite2D | Mesh3D] · Audio I/O · Input Hooks
```

No layer may import from a non-adjacent layer. All communication flows through a typed asynchronous event bus.

## Features

- **GUI-first configuration** — no `.json` editing required.
- **2D/3D hot-swap** — toggle between sprite and 3D mesh renderers without restart.
- **Fallback chain** — local LLM → cloud provider → offline persona.
- **Voice pipeline** — local STT (Whisper) + TTS (Piper) with streaming.
- **Atomic state persistence** — crash-safe writes, automatic recovery.
- **Safe Mode** — degrades gracefully instead of crashing.
- **Watchdog sidecar** — detects freezes and offers relaunch.
- **Privacy-first** — screen awareness defaults OFF; all AI local by default.

## Documentation

- [Master Specification](./SPECIFICATION.md) — the canonical engineering blueprint.
- Architecture docs in `docs/architecture.md` (generated from source).

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run linting and type checking
uv run ruff check src/
uv run mypy src/

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/chimera --cov-report=html
```

## License

MIT — see [LICENSE](./LICENSE) for details.

## Credits

Chimera is a clean-room synthesis of two antecedent projects. See [CREDITS.md](./CREDITS.md) and [REFERENCES.md](./REFERENCES.md) for full attribution.