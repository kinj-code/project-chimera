"""FileProcessor — handles drag-and-drop file ingestion into the RAG pipeline.

Subscribes to FileDropEvent on the EventBus. When a file is dropped,
it ingests it into the RAGManager and provides UI feedback via SpeakRequest.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from chimera.bridge.events import FileDropEvent, SpeakRequest, Emotion

if TYPE_CHECKING:
    pass


class FileProcessor:
    """Watches for dropped files and feeds them into the RAG pipeline."""

    def __init__(self, bus: object, rag_manager: object) -> None:
        """Initialize the file processor.

        Args:
            bus: The EventBus instance.
            rag_manager: A RAGManager instance for document ingestion.
        """
        self._bus = bus
        self._rag = rag_manager
        logger.info("FileProcessor initialized")

    async def attach(self) -> None:
        """Subscribe to FileDropEvent on the bus."""
        self._bus.subscribe(FileDropEvent, self._on_file_drop)  # type: ignore[arg-type]
        logger.info("FileProcessor attached to EventBus (FileDropEvent)")

    async def _on_file_drop(self, event: FileDropEvent) -> None:
        """Handle a file drop event by ingesting each file into RAG.

        Args:
            event: The FileDropEvent with file_paths.
        """
        supported = {".pdf", ".docx", ".txt", ".md", ".pptx", ".xlsx", ".csv",
                     ".html", ".htm", ".json", ".xml", ".rtf", ".epub"}

        for file_path in event.file_paths:
            logger.info(f"File dropped: {file_path}")
            filename = file_path.split("/")[-1] if "/" in file_path else file_path
            ext = f".{filename.split('.')[-1]}" if "." in filename else ""

            # Check extension FIRST — reject unsupported before "Ingesting".
            if ext and ext.lower() not in supported:
                logger.warning(f"Unsupported file type: {ext}")
                await self._bus.publish(  # type: ignore[union-attr]
                    SpeakRequest(
                        text=f"⚠️ I can't read {ext} files yet. I support PDF, DOCX, and TXT. Try dropping a text document!",
                        interrupt=False,
                        emotion=Emotion.NEUTRAL,
                    )
                )
                continue

            # Show "ingesting" indicator ONLY for supported files.
            await self._bus.publish(  # type: ignore[union-attr]
                SpeakRequest(
                    text=f"📄 Ingesting {filename}...",
                    interrupt=False,
                    emotion=Emotion.NEUTRAL,
                )
            )

            # Run ingestion in background thread.
            try:
                result = await self._rag.ingest_file(file_path)  # type: ignore[union-attr]
            except Exception as exc:
                logger.error(f"Ingestion failed for {file_path}: {exc}")
                result = f"❌ Failed to process {filename}"

            # Show result as a SpeakRequest (appears in chat log).
            await self._bus.publish(  # type: ignore[union-attr]
                SpeakRequest(
                    text=result,
                    interrupt=False,
                    emotion=Emotion.HAPPY if "✅" in result else Emotion.NEUTRAL,
                )
            )
