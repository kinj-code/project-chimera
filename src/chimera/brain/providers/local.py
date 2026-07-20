"""LocalLLMProvider — real LLM inference using llama.cpp with Qwen2 0.5B.

Subscribes to TextInputEvent, generates responses in a background thread
to keep the UI responsive, then publishes SpeakRequest + MoodChange.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from chimera.bridge.events import Emotion, MoodChange, SpeakRequest, TextInputEvent

if TYPE_CHECKING:
    from llama_cpp import Llama


class LocalLLMProvider:
    """A real LLM provider backed by llama.cpp and a local GGUF model.

    LLM generation runs in a separate thread via asyncio.to_thread to
    prevent UI freezes. The main window shows "Chimera is thinking..."
    during generation.
    """

    # Chat template for Qwen2 Instruct models.
    CHAT_TEMPLATE = (
        "<|im_start|>system\n"
        "You are a friendly AI desktop companion named Chimera. "
        "Keep responses short, warm, and conversational. "
        "One to three sentences maximum.<|im_end|>\n"
        "<|im_start|>user\n"
        "{prompt}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

    def __init__(
        self,
        bus: object,
        model_path: str | Path | None = None,
        n_ctx: int = 2048,
        n_threads: int = 4,
        temperature: float = 0.8,
        rag_manager: object | None = None,
        os_awareness: object | None = None,
    ) -> None:
        """Initialize the local LLM provider.

        Args:
            bus: The EventBus instance.
            model_path: Path to the GGUF model file. Auto-detected if None.
            n_ctx: Context window size in tokens.
            n_threads: CPU threads for inference.
            temperature: Sampling temperature (0.0-2.0).
            rag_manager: Optional RAGManager for document-aware responses.
            os_awareness: Optional OSAwarenessManager for screen/process/app access.
        """
        self._bus = bus
        self._temperature = temperature
        self._persona: str = "Friendly"
        self._rag = rag_manager
        self._os = os_awareness

        # Resolve model path.
        if model_path is None:
            model_path = self._find_model()
        self._model_path: Path = Path(model_path)
        self._llm: Llama | None = None
        self._load_lock = threading.Lock()
        self._n_ctx = n_ctx
        self._n_threads = n_threads

        logger.info(f"LocalLLMProvider configured: {self._model_path}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def attach(self) -> None:
        """Subscribe to the event bus and load the model in background."""
        self._bus.subscribe(TextInputEvent, self._on_text_input)  # type: ignore[arg-type]
        logger.info("LocalLLMProvider attached to EventBus")

        # Load the model in a background thread so the UI isn't blocked.
        logger.info("Loading LLM model in background...")
        await asyncio.to_thread(self._load_model)
        logger.success("LLM model loaded and ready!")

        # Send welcome message.
        asyncio.create_task(self._send_welcome())

    async def _send_welcome(self) -> None:
        """Send a welcome message 2 seconds after launch."""
        await asyncio.sleep(2.0)
        speak = SpeakRequest(
            text="I'm awake! How can I help you today?",
            interrupt=False,
            emotion=Emotion.HAPPY,
        )
        try:
            await self._bus.publish(speak)  # type: ignore[union-attr]
        except RuntimeError:
            pass

    def set_persona(self, persona: str) -> None:
        """Update the system prompt persona.

        Args:
            persona: One of "Friendly", "Sarcastic", "Professional",
                     or a custom persona string.
        """
        self._persona = persona
        logger.info(f"Persona set to: {persona}")

    def set_temperature(self, temperature: float) -> None:
        """Update the sampling temperature.

        Args:
            temperature: 0.0 (deterministic) to 1.0 (creative).
        """
        self._temperature = max(0.0, min(1.0, temperature))
        logger.info(f"Temperature set to: {self._temperature}")

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _find_model(self) -> Path:
        """Auto-discover the GGUF model file in the assets directory."""
        candidates = [
            Path("assets/qwen2-0_5b-instruct-q4_k_m.gguf"),
            Path("assets/models/qwen2-0_5b-instruct-q4_k_m.gguf"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError(
            "No GGUF model found. Download one to assets/ "
            "or pass model_path to LocalLLMProvider()."
        )

    def _load_model(self) -> None:
        """Load the GGUF model into memory. Runs in a background thread."""
        with self._load_lock:
            if self._llm is not None:
                return  # Already loaded.

            from llama_cpp import Llama

            logger.info(f"Loading model from {self._model_path}...")
            self._llm = Llama(
                model_path=str(self._model_path),
                n_ctx=self._n_ctx,
                n_threads=self._n_threads,
                verbose=False,
            )
            logger.info("Model loaded into memory.")

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_text_input(self, event: TextInputEvent) -> None:
        """Handle a user text input event by generating an LLM response.

        Args:
            event: The TextInputEvent from the EventBus.
        """
        prompt_text = event.text.strip()
        if not prompt_text:
            return

        logger.info(f"LLM input: '{prompt_text}'")

        # --- RAG gating: only query RAG if the user seems to be asking about documents ---
        rag_keywords = ["document", "file", "pdf", "summarize", "what is this",
                        "doc", "txt", "read", "ingest", "uploaded", "dropped"]
        rag_context = ""
        if any(kw in prompt_text.lower() for kw in rag_keywords):
            rag_context = await self._run_rag_query(prompt_text)

        # --- Tool calling: intercept user intent before LLM generation ---
        os_context = await self._run_os_tools(prompt_text)

        # Build the Qwen2 chat template prompt with active persona.
        custom_personas = {
            "Friendly": "You are Chimera. You are upbeat, friendly, and use emojis occasionally.",
            "Sarcastic": "You are Chimera. You are highly sarcastic, witty, and a bit snarky. You still help, but with an attitude.",
            "Professional": "You are Chimera. You are strictly professional, concise, and formal. No jokes.",
        }
        # If persona isn't one of the 3 presets, treat it as a custom instruction.
        if self._persona in custom_personas:
            persona_instruction = custom_personas[self._persona]
        else:
            persona_instruction = f"You are Chimera. {self._persona}"

        base_prompt = (
            f"{persona_instruction} "
            "You CAN see the user's screen via OCR text extraction when asked. "
            "You CAN list running applications. You CAN open apps. "
            "Use the provided context to answer accurately. "
            "If context is provided for a question about the screen or processes, use it. "
            "Keep responses under 2 sentences."
        )
        # Layer: OS context first (highest priority), then RAG context.
        combined_context = ""
        if os_context:
            combined_context += f"OS CONTEXT:\n{os_context}\n\n"
        if rag_context:
            combined_context += f"DOCUMENT CONTEXT:\n{rag_context}\n\n"

        if combined_context:
            system_prompt = (
                f"Use the following context to answer the user's question:\n\n"
                f"{combined_context}"
                f"---\n"
                f"{base_prompt}"
            )
        else:
            system_prompt = base_prompt
        formatted_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt_text}<|im_end|>\n<|im_start|>assistant\n"

        # Run LLM generation in a background thread.
        try:
            response_text = await asyncio.to_thread(self._generate, formatted_prompt)
        except Exception as exc:
            logger.error(f"LLM generation failed: {exc}")
            response_text = "Sorry, I had trouble thinking. Try again?"

        # Emit mood change → CompanionOverlay shows happy face.
        mood = MoodChange(
            previous=Emotion.NEUTRAL,
            current=Emotion.HAPPY,
            intensity=1.0,
            transition_ms=400,
            cause="user_input",
        )
        await self._bus.publish(mood)  # type: ignore[union-attr]

        # Emit speech → MainWindow displays response + voice speaks.
        speak = SpeakRequest(
            text=response_text,
            interrupt=False,
            emotion=Emotion.HAPPY,
        )
        await self._bus.publish(speak)  # type: ignore[union-attr]

        logger.info(f"LLM response: '{response_text}'")

    def _generate(self, prompt: str) -> str:
        """Run generation synchronously (called via asyncio.to_thread).

        Args:
            prompt: The formatted chat template prompt.

        Returns:
            The generated response text, stripped of whitespace.
        """
        if self._llm is None:
            return "I'm still waking up. Give me a moment."

        output = self._llm(
            prompt,
            max_tokens=128,
            temperature=self._temperature,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=["<|im_end|>", "<|im_start|>", "\n\n"],
            echo=False,
        )

        raw = output["choices"][0]["text"].strip()
        # Remove trailing incomplete sentences.
        if raw and not raw.endswith((".", "!", "?", "。", "！", "？")):
            # Truncate to last complete sentence.
            last_period = max(raw.rfind("."), raw.rfind("!"), raw.rfind("?"))
            if last_period > 10:  # Ensure we have at least some content.
                raw = raw[: last_period + 1]

        return raw or "I'm not sure what to say to that."

    # ------------------------------------------------------------------
    # Tool calling helpers
    # ------------------------------------------------------------------

    async def _run_os_tools(self, prompt: str) -> str:
        """Run OS awareness tools based on keyword matching.

        Args:
            prompt: The user's input text.

        Returns:
            Tool results as a combined context string, or empty string.
        """
        if self._os is None:
            return ""

        results: list[str] = []
        lower = prompt.lower()

        # Time tool: inject real time if user asks.
        time_keywords = ["time", "clock", "what time", "current time"]
        if any(kw in lower for kw in time_keywords):
            from datetime import datetime
            now = datetime.now().strftime("%I:%M %p")
            results.append(f"The current time is {now}.")

        # Screen OCR keywords.
        screen_keywords = [
            "screen", "see", "display", "what's on my", "looking at",
            "read my screen", "what does my screen say", "scan my display",
        ]
        if any(kw in lower for kw in screen_keywords):
            logger.info("Tool: capturing screen OCR")
            screen_text = await self._os.capture_screen()  # type: ignore[union-attr]
            results.append(f"Screen text (OCR):\n{screen_text}")

        # File system keywords.
        fs_keywords = [
            "folder", "directory", "files in", "downloads", "desktop",
            "documents", "list items", "what's in my",
        ]
        if any(kw in lower for kw in fs_keywords):
            import os as _os
            target_dir = None
            if "download" in lower:
                target_dir = _os.path.expanduser("~/Downloads")
            elif "desktop" in lower:
                target_dir = _os.path.expanduser("~/Desktop")
            elif "document" in lower:
                target_dir = _os.path.expanduser("~/Documents")
            if target_dir and _os.path.isdir(target_dir):
                try:
                    items = _os.listdir(target_dir)[:20]
                    item_list = ", ".join(items)
                    results.append(f"Contents of {target_dir}: {item_list}")
                except Exception:
                    pass

        # Process list — with formatting hint so LLM summarizes nicely.
        process_keywords = [
            "apps", "running", "processes", "programs", "applications",
        ]
        if any(kw in lower for kw in process_keywords):
            logger.info("Tool: listing processes")
            proc_list = await self._os.list_processes()  # type: ignore[union-attr]
            results.append(
                f"The user asked what apps are running. Here is the list: "
                f"{proc_list}. Please summarize this list for the user."
            )

        # App launch.
        launch_keywords = ["open ", "launch "]
        for kw in launch_keywords:
            if kw in lower:
                idx = lower.find(kw) + len(kw)
                app_name = prompt[idx:].strip().split()[0] if idx < len(prompt) else ""
                if app_name:
                    logger.info(f"Tool: launching {app_name}")
                    launch_result = await self._os.launch_application(app_name)  # type: ignore[union-attr]
                    results.append(
                        f"App launch result for '{app_name}': {launch_result}"
                    )

        return "\n".join(results) if results else ""

    async def _run_rag_query(self, prompt: str) -> str:
        """Query RAG for relevant document context.

        Args:
            prompt: The user's input text.

        Returns:
            Retrieved document context, or empty string.
        """
        if self._rag and hasattr(self._rag, 'query_context'):
            return await self._rag.query_context(prompt)  # type: ignore[union-attr]
        return ""

    def _get_persona_instructions(self) -> str:
        """Return persona-specific instructions for the system prompt."""
        personas = {
            "Friendly": "Be warm, encouraging, and supportive. Use emoji occasionally.",
            "Sarcastic": "Be witty and slightly sarcastic. Use dry humor. Don't be mean.",
            "Professional": "Be formal, precise, and helpful. Avoid casual language.",
        }
        return personas.get(self._persona, personas["Friendly"])
