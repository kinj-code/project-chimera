"""Smoke test: launch Chimera 5 times headlessly, type 'hello', verify response."""

import asyncio
import sys
from pathlib import Path

# Ensure src/ is on path.
_SRC = Path(__file__).resolve().parent.parent.parent / "src"
sys.path.insert(0, str(_SRC))

from chimera.bridge.bus import EventBus
from chimera.brain.providers.offline import StubLLMProvider
from chimera.bridge.events import SpeakRequest, TextInputEvent


_RESULTS = []


async def _run_one(n: int) -> bool:
    """Run a single smoke-test iteration headlessly.

    Returns True on PASS, False on FAIL.
    """
    try:
        bus = EventBus()
        await bus.start()

        response_future: asyncio.Future[str] = asyncio.Future()

        async def _on_speak(event: SpeakRequest) -> None:
            if not response_future.done():
                response_future.set_result(event.text)

        bus.subscribe(SpeakRequest, _on_speak)  # type: ignore[arg-type]

        stub = StubLLMProvider(bus)
        await stub.attach()

        # Simulate user typing "hello".
        await bus.publish(TextInputEvent(text="hello"))

        # Wait up to 5s for a response.
        response = await asyncio.wait_for(response_future, timeout=5.0)

        assert response, "Empty response"
        print(f"  [{n}] PASS — response: {response!r}")

        return True
    except Exception as exc:
        print(f"  [{n}] FAIL — {exc}")
        return False
    finally:
        await bus.shutdown()  # type: ignore[union-attr]


async def main() -> None:
    for i in range(1, 6):
        ok = await _run_one(i)
        _RESULTS.append(ok)

    passed = sum(_RESULTS)
    failed = len(_RESULTS) - passed
    print(f"\nSMOKE TEST COMPLETE: {passed}/5 PASS, {failed}/5 FAIL")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())