# Credits

Project Chimera is a clean-room redevelopment that preserves validated logic from two antecedent systems while discarding their architectural debt. We gratefully acknowledge the prior work that made this project possible.

## Brain Donor: Bubby

**Source:** `kinj-code/bubby`

Bubby contributed the core concepts and partial implementations for:

- Asynchronous behavior tree execution
- Three-tier memory architecture (short-term / episodic / long-term)
- Perception module design (screen context, file drop, window tracking)
- Intent parsing patterns for action dispatch
- Event-driven interaction loop

Bubby's autonomy model — idle loops, reactive gestures, and scheduled "ping" behaviors — directly informs Chimera's Brain layer. Its behavior tree patterns have been refactored for async execution and decoupled from any renderer dependency.

## Heart Donor: Riko Project

**Source:** `rayenfeng/riko_project`

Riko contributed the validated conversational pipeline architecture:

- LLM + Whisper + TTS integration patterns
- 3D character rendering with ModernGL
- Gesture-to-emotion synchronization model
- Morph target blending for facial expressions
- Streaming audio pipeline design

Riko proved that local-first AI companions are viable on consumer hardware. Chimera preserves Riko's pipeline logic while replacing its monolithic coupling with the Brain-Bridge-Body topology.

## Third-Party Libraries

Chimera depends on the following open-source projects (full dependency list in `pyproject.toml`):

| Library | Purpose | License |
|---|---|---|
| PySide6 | Qt GUI framework | LGPL |
| qasync | asyncio/Qt event loop bridge | BSD |
| ModernGL | 3D rendering | MIT |
| pygltflib | glTF 2.0 asset loading | MIT |
| llama-cpp-python | Local LLM inference | MIT |
| faster-whisper | Speech-to-text | MIT |
| Piper | Text-to-speech | MIT |
| pynput | Global input hooks | LGPL |
| Pydantic | Data validation | MIT |
| loguru | Structured logging | MIT |
| PyYAML | Configuration parsing | MIT |
| pytest | Testing framework | MIT |

## Engineering Team

Project Chimera — Office of the CTO / Lead Architect, 2026.

*"We stand on the shoulders of giants, but we build our own footing."*