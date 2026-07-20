# References

Annotated bibliography of papers, repositories, and design patterns that inform Project Chimera's architecture.

## Architectural Patterns

### Event-Driven Architecture (EDA)

- **Hohpe, G., & Woolf, B. (2004).** *Enterprise Integration Patterns.* Addison-Wesley.
  - Foundational patterns for message routing, publish/subscribe, and event buses. Chimera's typed EventBus (`bridge/bus.py`) follows the Message Channel and Publish-Subscribe Channel patterns.

- **Fowler, M. (2017).** *Event-Driven Architecture.* martinfowler.com.
  - Guidance on when to use events vs. request/response. Chimera uses events for Brain→Body dispatch and request/response for configuration queries.

### Behavior Trees

- **Colledanchise, M., & Ögren, P. (2018).** *Behavior Trees in Robotics and AI: An Introduction.* CRC Press.
  - Definitive reference for behavior tree design. Chimera's Brain behavior module (`brain/behavior/`) follows the selector/sequence/decorator pattern from this text.

- **py_trees library** — https://github.com/splintered-reality/py_trees
  - Reference implementation of behavior trees in Python. Chimera's async behavior tree is modeled on py_trees' architecture but adapted for asyncio.

### Observer / Pub-Sub in GUI Applications

- **Qt Signals & Slots documentation** — https://doc.qt.io/qt-6/signalsandslots.html
  - Chimera's EventBus provides a Qt-independent pub/sub layer. The Bridge translates between Qt signals (UI) and Pydantic events (Brain).

- **qasync** — https://github.com/CabbageDevelopment/qasync
  - The critical bridge between Python's asyncio and Qt's event loop. Chimera depends on qasync to keep the UI responsive during LLM inference.

## AI & ML Infrastructure

### Local LLM Inference

- **llama.cpp** — https://github.com/ggerganov/llama.cpp
  - CPU-first LLM inference in C/C++. Chimera uses `llama-cpp-python` bindings with GGUF quantization. The separate-process loading strategy in Section 6.2 of the spec is directly informed by llama.cpp's memory behavior.

- **Grama, A., et al. (2024).** *GGUF: GGML Universal Format.* — https://github.com/ggerganov/ggml
  - The GGUF quantization format enables Chimera to run 7B models on consumer laptops. The `Q4_K_M` default in config comes from this family.

### Speech-to-Text

- **faster-whisper** — https://github.com/SYSTRAN/faster-whisper
  - CTranslate2-based reimplementation of OpenAI Whisper. 4× faster inference than the reference implementation. Chimera uses this for local, private STT.

### Text-to-Speech

- **Piper TTS** — https://github.com/rhasspy/piper
  - Fast, local neural TTS with streaming synthesis. Chimera's TTS wrapper (`body/audio/tts.py`) uses Piper for sentence-boundary streaming.

### Vector Memory

- **FAISS** — https://github.com/facebookresearch/faiss
  - Facebook AI Similarity Search. Used for Chimera's long-term memory semantic retrieval when `long_term.engine == "faiss"`.

- **ChromaDB** — https://github.com/chroma-core/chroma
  - Alternative local vector database. Available as an optional long-term memory backend.

## Graphics & Rendering

### 3D Rendering

- **ModernGL** — https://github.com/moderngl/moderngl
  - Pythonic OpenGL wrapper. Chimera's `Mesh3DRenderer` uses ModernGL for shader-based rendering without a game engine.

- **glTF 2.0 Specification** — https://registry.khronos.org/glTF/
  - The asset format for 3D characters. Chimera character packs use glTF with morph targets for facial animation.

- **pygltflib** — https://github.com/dodgyville/pygltflib
  - Python library for parsing glTF 2.0 files. Used in `body/renderers/mesh3d.py` for asset loading.

### 2D Rendering

- **Qt Graphics View Framework** — https://doc.qt.io/qt-6/graphicsview.html
  - Chimera's `Sprite2DRenderer` uses QGraphicsScene with sprite atlas sheets. The Graphics View Framework provides hardware-accelerated 2D rendering with minimal overhead.

## Design Patterns Used

| Pattern | Location | Rationale |
|---|---|---|
| **Protocol (Structural Subtyping)** | `body/renderers/abstract.py` | Renderer-agnostic dispatch without inheritance |
| **Registry** | `bridge/registry.py` | Plugin discovery for renderers, LLM providers, skills |
| **Adapter** | Bridge → Renderer translation | Abstract ActionIntent → Concrete RenderCommand |
| **Chain of Responsibility** | `brain/orchestrator.py` | LLM fallback: local → cloud → offline |
| **Observer (Pub/Sub)** | `bridge/bus.py` | Decoupled Brain/Bridge/Body communication |
| **Memento** | `bridge/state.py` | Atomic state persistence with rollback |
| **Strategy** | LLM provider interface | Swappable LLM backends (local, cloud, offline) |
| **Singleton** | `EventBus`, `StateManager` | Single canonical bus and state per process |

## Prior Art

- **Desktop Mascot Systems** (e.g., Microsoft Agent, Clippy, BonziBuddy):
  Chimera intentionally avoids the "office assistant" UX trap by focusing on ambient presence rather than unsolicited advice. The companion only speaks when spoken to by default.

- **AI Companion Projects** (e.g., Replika, Character.AI, Nomi):
  These are cloud-only and conversation-only. Chimera differentiates by being local-first, renderer-agnostic, and context-aware (screen, files, window focus).

- **Virtual YouTuber / VTuber Software** (e.g., VSeeFace, Live2D Cubism):
  Focused on streaming rather than ambient desktop presence. Chimera borrows their facial tracking concepts but inverts the pipeline (AI drives the avatar, not a camera).

## Further Reading

- *Building Event-Driven Microservices* by Adam Bellemare (O'Reilly, 2020) — applicable patterns for event schema design and versioning.
- *Game Engine Architecture* by Jason Gregory (CRC Press, 3rd ed.) — chapter on animation blending directly informs Chimera's MoodState transition design.
- *Designing Data-Intensive Applications* by Martin Kleppmann (O'Reilly, 2017) — chapters on encoding, replication, and consensus inform the StateManager's atomic write strategy.