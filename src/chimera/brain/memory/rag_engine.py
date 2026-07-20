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
        self._doc_collections: dict[str, chromadb.Collection] = {}
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

        # 3. Generate IDs with timestamp for uniqueness.
        import time as _time
        doc_id = file_path.stem.replace(" ", "_")
        ts = int(_time.time())
        ids = [f"{doc_id}_{ts}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": str(file_path), "chunk": i, "file": file_path.name} for i in range(len(chunks))]

        # 4. Upsert into ChromaDB (thread-safe).
        with self._lock:
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

    async def query_context(self, query_text: str, k: int = 3, document_id: str | None = None) -> str:
        """Search the vector database for relevant document chunks.

        Args:
            query_text: The user's question.
            k: Number of top chunks to retrieve.
            document_id: Optional document ID to filter results to a specific document.

        Returns:
            Concatenated context string, or empty string if nothing found.
        """
        return await asyncio.to_thread(self._query_blocking, query_text, k, document_id)

    def _query_blocking(self, query_text: str, k: int, document_id: str | None = None) -> str:
        """Query ChromaDB and return concatenated context. Runs in a thread."""
        if not self._ready or self._collection is None:
            return ""

        with self._lock:
            if self._collection.count() == 0:
                return ""

            try:
                # Filter by document_id if specified
                where_clause = {"file": document_id} if document_id else None
                
                results = self._collection.query(
                    query_texts=[query_text],
                    n_results=min(k, self._collection.count()),
                    where=where_clause,
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
        """Parse a file based on its extension. Supports 10+ formats."""
        suffix = file_path.suffix.lower()
        parsers = {
            ".txt": lambda p: p.read_text(encoding="utf-8", errors="replace"),
            ".md": lambda p: p.read_text(encoding="utf-8", errors="replace"),
            ".json": lambda p: p.read_text(encoding="utf-8", errors="replace"),
            ".xml": lambda p: p.read_text(encoding="utf-8", errors="replace"),
            ".html": self._parse_html,
            ".htm": self._parse_html,
            ".csv": self._parse_csv,
            ".pdf": self._parse_pdf,
            ".docx": self._parse_docx,
            ".pptx": self._parse_pptx,
            ".xlsx": self._parse_xlsx,
            ".rtf": self._parse_rtf,
            ".epub": self._parse_epub,
        }
        parser = parsers.get(suffix)
        if parser is None:
            logger.warning(f"Unsupported file type: {suffix} — attempting plain text read.")
            try:
                return file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return ""
        try:
            return parser(file_path)
        except Exception as exc:
            logger.error(f"Failed to parse {file_path}: {exc}")
            return ""

    @staticmethod
    def _parse_pdf(path: Path) -> str:
        """Extract text from a PDF file. Tries pypdf first, then pdfminer."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)
        except Exception as exc:
            logger.warning(f"pypdf failed ({exc}), trying pdfminer fallback...")
            try:
                from pdfminer.high_level import extract_text as pdfminer_extract
                return pdfminer_extract(str(path))
            except ImportError:
                logger.error("pdfminer not installed. Cannot parse PDF files.")
                return ""
            except Exception as exc2:
                logger.error(f"Both PDF parsers failed: {exc2}")
                return ""

    @staticmethod
    def _parse_docx(path: Path) -> str:
        """Extract text from a DOCX file."""
        try:
            import docx2txt
            return docx2txt.process(str(path))
        except ImportError:
            logger.error("docx2txt not installed.")
            return ""

    @staticmethod
    def _parse_html(path: Path) -> str:
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser").get_text()
        except ImportError:
            return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _parse_csv(path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _parse_pptx(path: Path) -> str:
        try:
            from pptx import Presentation
            prs = Presentation(str(path))
            return "\n".join(slide_text(shape) for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text"))
        except ImportError:
            logger.error("python-pptx not installed.")
            return ""
        def slide_text(shape):
            return shape.text

    @staticmethod
    def _parse_xlsx(path: Path) -> str:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True)
            rows = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    rows.append(" ".join(str(c) for c in row if c))
            return "\n".join(rows)
        except ImportError:
            logger.error("openpyxl not installed.")
            return ""

    @staticmethod
    def _parse_rtf(path: Path) -> str:
        try:
            from striprtf.striprtf import rtf_to_text
            return rtf_to_text(path.read_text(encoding="utf-8", errors="replace"))
        except ImportError:
            return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _parse_epub(path: Path) -> str:
        try:
            from ebooklib import epub
            book = epub.read_epub(str(path))
            docs = []
            for item in book.get_items_of_type(9):  # ITEM_DOCUMENT = 9
                from bs4 import BeautifulSoup
                docs.append(BeautifulSoup(item.get_content().decode("utf-8", errors="replace"), "html.parser").get_text())
            return "\n".join(docs)
        except ImportError:
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