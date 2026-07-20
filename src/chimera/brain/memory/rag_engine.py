"""RAGManager — local document ingestion and semantic retrieval.

Uses ChromaDB for vector storage with sentence-transformers embeddings.
Processes .txt, .pdf, .docx files. All ingestion runs in background threads.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    pass


class RAGManager:
    """Manages a local RAG pipeline for document-aware LLM responses.

    Usage:
        rag = RAGManager()
        await rag.ingest_file("/path/to/doc.pdf")
        context = await rag.query("What is this document about?")
    """

    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    DB_PATH = "./data/chroma_db"

    def __init__(self, persist_dir: str | None = None) -> None:
        self._persist_dir = persist_dir or self.DB_PATH
        self._client = None
        self._collection = None
        self._ef = None
        self._ready = False
        self._lock = threading.Lock()
        self._init_backend()

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Backend initialization
    # ------------------------------------------------------------------

    def _init_backend(self) -> None:
        """Initialize ChromaDB client and embedding function."""
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self._client = chromadb.PersistentClient(path=self._persist_dir)

            # Use the default sentence-transformers embedding function.
            try:
                self._ef = embedding_functions.DefaultEmbeddingFunction()
                # Warm up: call once to trigger model download if needed.
                _ = self._ef(["test"])
            except Exception:
                logger.warning(
                    "DefaultEmbeddingFunction not available (sentence-transformers "
                    "may not be installed). Falling back to ChromaDB's built-in "
                    "ONNX embedding function."
                )
                self._ef = embedding_functions.ONNXMiniLM_L6_V2()

            self._collection = self._client.get_or_create_collection(
                name="chimera_documents",
                embedding_function=self._ef,
            )
            self._ready = True
            count = self._collection.count()
            logger.info(
                f"RAGManager ready. Collection 'chimera_documents' has {count} chunks."
            )
        except Exception as exc:
            logger.error(f"RAGManager backend initialization failed: {exc}")
            self._ready = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest_file(self, file_path: str | Path) -> str:
        """Ingest a document file into the vector database.

        Args:
            file_path: Path to a .txt, .pdf, or .docx file.

        Returns:
            A human-readable status message.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return f"❌ File not found: {file_path.name}"

        # Run parsing and embedding in background thread.
        return await asyncio.to_thread(self._ingest_blocking, file_path)

    def _ingest_blocking(self, file_path: Path) -> str:
        """Parse, chunk, embed, and store a document. Runs in a thread."""
        if not self._ready or self._collection is None:
            return "❌ RAG engine is not initialized. Check logs."

        # 1. Parse.
        text = self._parse_file(file_path)
        if not text:
            return f"❌ Could not extract text from {file_path.name}"

        # 2. Chunk.
        chunks = self._chunk_text(text)
        if not chunks:
            return f"❌ No content to index in {file_path.name}"

        # 3. Generate IDs.
        doc_id = file_path.stem.replace(" ", "_")
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": str(file_path), "chunk": i} for i in range(len(chunks))]

        # 4. Upsert into ChromaDB.
        try:
            self._collection.upsert(
                ids=ids,
                documents=chunks,
                metadatas=metadatas,
            )
            logger.info(f"Ingested '{file_path.name}': {len(chunks)} chunks.")
        except Exception as exc:
            logger.error(f"ChromaDB upsert failed: {exc}")
            return f"❌ Failed to index {file_path.name}"

        return f"✅ Indexed {file_path.name} ({len(chunks)} chunks). Ask me anything!"

    async def query_context(self, query_text: str, k: int = 3) -> str:
        """Search the vector database for relevant document chunks.

        Args:
            query_text: The user's question.
            k: Number of top chunks to retrieve.

        Returns:
            Concatenated context string, or empty string if nothing found.
        """
        return await asyncio.to_thread(self._query_blocking, query_text, k)

    def _query_blocking(self, query_text: str, k: int) -> str:
        """Query ChromaDB and return concatenated context. Runs in a thread."""
        if not self._ready or self._collection is None:
            return ""

        if self._collection.count() == 0:
            return ""

        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(k, self._collection.count()),
            )
            docs = results.get("documents", [[]])[0]
            if not docs:
                return ""
            return "\n\n---\n\n".join(docs)
        except Exception as exc:
            logger.error(f"RAG query failed: {exc}")
            return ""

    def get_document_count(self) -> int:
        """Return the number of stored document chunks."""
        if self._collection is not None:
            return self._collection.count()
        return 0

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_file(self, file_path: Path) -> str:
        """Parse a file based on its extension."""
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".txt":
                return file_path.read_text(encoding="utf-8")
            elif suffix == ".pdf":
                return self._parse_pdf(file_path)
            elif suffix == ".docx":
                return self._parse_docx(file_path)
            else:
                logger.warning(f"Unsupported file type: {suffix}")
                return ""
        except Exception as exc:
            logger.error(f"Failed to parse {file_path}: {exc}")
            return ""

    @staticmethod
    def _parse_pdf(path: Path) -> str:
        """Extract text from a PDF file."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)
        except ImportError:
            logger.error("pypdf not installed. Cannot parse PDF files.")
            return ""

    @staticmethod
    def _parse_docx(path: Path) -> str:
        """Extract text from a DOCX file."""
        try:
            import docx2txt

            return docx2txt.process(str(path))
        except ImportError:
            logger.error("docx2txt not installed. Cannot parse DOCX files.")
            return ""

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks.

        Args:
            text: The full document text.

        Returns:
            List of text chunks.
        """
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.CHUNK_SIZE
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += self.CHUNK_SIZE - self.CHUNK_OVERLAP
        return chunks