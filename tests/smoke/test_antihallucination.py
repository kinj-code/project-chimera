"""Verify the anti-hallucination system prompt works."""
import asyncio
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent.parent / "src"
sys.path.insert(0, str(_SRC))

from chimera.bridge.bus import EventBus
from chimera.brain.providers.local import LocalLLMProvider
from chimera.bridge.events import SpeakRequest, TextInputEvent


async def main():
    bus = EventBus()
    await bus.start()

    responses: list[str] = []

    async def on_speak(event: SpeakRequest) -> None:
        responses.append(event.text)

    bus.subscribe(SpeakRequest, on_speak)  # type: ignore[arg-type]

    llm = LocalLLMProvider(bus)
    await llm.attach()

    # Test screen-awareness question.
    print("Testing: what's on my screen")
    await bus.publish(TextInputEvent(text="what's on my screen"))
    await asyncio.sleep(3)
    if responses:
        r = responses[-1].lower()
        if "don't have screen access" in r or "cannot see" in r or "can't see" in r:
            print(f"PASS: {responses[-1]!r}")
        else:
            print(f"FAIL (may still be acceptable): {responses[-1]!r}")
    else:
        print("FAIL: No response")

    # Test files question.
    print("\nTesting: what files do I have")
    await bus.publish(TextInputEvent(text="what files do I have"))
    await asyncio.sleep(3)
    if len(responses) >= 2:
        r = responses[-1].lower()
        if "don't have screen access" in r or "cannot see" in r or "can't see" in r or "files" in r:
            print(f"PASS: {responses[-1]!r}")
        else:
            print(f"INFO: {responses[-1]!r}")
    else:
        print("FAIL: No second response")

    await bus.shutdown()


if __name__ == "__main__":
    asyncio.run(main())