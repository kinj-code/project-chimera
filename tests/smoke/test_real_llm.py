"""Integration test: full pipeline with real LocalLLMProvider."""
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

    response_future: asyncio.Future[str] = asyncio.Future()

    async def on_speak(event: SpeakRequest) -> None:
        if not response_future.done():
            response_future.set_result(event.text)

    bus.subscribe(SpeakRequest, on_speak)  # type: ignore[arg-type]

    llm = LocalLLMProvider(bus)
    await llm.attach()

    print("LLM loaded. Sending 'hello'...")
    await bus.publish(TextInputEvent(text="hello"))

    try:
        response = await asyncio.wait_for(response_future, timeout=30.0)
        print(f"\nREAL LLM RESPONSE: {response!r}")
        assert len(response) > 3, "Response too short"
        print("\nPASS: Real LLM returned a meaningful response.")
    except asyncio.TimeoutError:
        print("\nFAIL: LLM timed out after 30s.")
        sys.exit(1)
    except Exception as exc:
        print(f"\nFAIL: {exc}")
        sys.exit(1)
    finally:
        await bus.shutdown()


if __name__ == "__main__":
    asyncio.run(main())