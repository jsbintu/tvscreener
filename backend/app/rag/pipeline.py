"""
Bubby Vision — RAG Pipeline

Document ingestion and retrieval using ChromaDB.
Chunks text, stores embeddings, and queries for relevant context.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

# Default collection names
COLLECTION_MARKET_RESEARCH = "market_research"
COLLECTION_EARNINGS = "earnings_transcripts"
COLLECTION_USER_NOTES = "user_notes"


# ──────────────────────────────────────────────
# Text Chunking
# ──────────────────────────────────────────────


def chunk_text(
    text: str,
    max_chunk_size: int = 512,
    overlap: int = 64,
) -> list[str]:
    """Split text into overlapping chunks by sentence boundaries.

    Args:
        text: Raw text to chunk.
        max_chunk_size: Maximum characters per chunk.
        overlap: Number of trailing characters to carry into the next chunk.

    Returns:
        List of text chunks.
    """
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_len + sentence_len > max_chunk_size and current:
            chunk = " ".join(current)
            chunks.append(chunk)

            # Overlap: keep tail sentences
            overlap_text = chunk[-overlap:] if overlap else ""
            current = [overlap_text] if overlap_text else []
            current_len = len(overlap_text)

        current.append(sentence)
        current_len += sentence_len + 1  # +1 for space

    if current:
        chunks.append(" ".join(current))

    return chunks


# ──────────────────────────────────────────────
# RAG Pipeline
# ──────────────────────────────────────────────


class RAGPipeline:
    """Document retrieval pipeline backed by ChromaDB.

    Uses ChromaDB's default embedding model for zero-config operation.

    Usage::

        rag = get_rag_pipeline()
        rag.ingest("doc_123", "Full text of the document...", {"source": "SEC"})
        results = rag.query("What was Apple's revenue?", n_results=3)
    """

    def __init__(self, collection_name: str = COLLECTION_MARKET_RESEARCH):
        self._client = None
        self._collection = None
        self._collection_name = collection_name
        self._init_client()

    def _init_client(self):
        """Initialize ChromaDB HTTP client."""
        try:
            import chromadb

            settings = get_settings()
            self._client = chromadb.HttpClient(
                host=settings.chromadb_host,
                port=settings.chromadb_port,
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            log.info(
                "rag.connected",
                collection=self._collection_name,
                host=settings.chromadb_host,
            )
        except Exception as exc:
            log.warning("rag.connection_failed", error=str(exc))
            self._client = None
            self._collection = None

    @property
    def available(self) -> bool:
        return self._collection is not None

    def ingest(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
        chunk_size: int = 512,
    ) -> int:
        """Chunk and ingest a document into the vector store.

        Args:
            doc_id: Unique document identifier.
            text: Full document text.
            metadata: Optional metadata to attach to each chunk.
            chunk_size: Maximum characters per chunk.

        Returns:
            Number of chunks ingested.
        """
        if not self.available:
            log.warning("rag.ingest_skipped", reason="not connected")
            return 0

        chunks = chunk_text(text, max_chunk_size=chunk_size)
        if not chunks:
            return 0

        base_meta = metadata or {}
        base_meta["doc_id"] = doc_id

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({**base_meta, "chunk_index": i, "total_chunks": len(chunks)})

        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        log.info("rag.ingested", doc_id=doc_id, chunks=len(chunks))
        return len(chunks)

    def query(
        self,
        question: str,
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """Query for relevant document chunks.

        Args:
            question: Natural language query.
            n_results: Number of results to return.
            where: Optional ChromaDB where filter.

        Returns:
            List of dicts with keys: text, metadata, distance.
        """
        if not self.available:
            log.warning("rag.query_skipped", reason="not connected")
            return []

        query_params: dict[str, Any] = {
            "query_texts": [question],
            "n_results": n_results,
        }
        if where:
            query_params["where"] = where

        try:
            results = self._collection.query(**query_params)
        except Exception as exc:
            log.error("rag.query_failed", error=str(exc))
            return []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        output = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            output.append({
                "text": doc,
                "metadata": meta,
                "distance": round(dist, 4),
            })

        return output

    def delete(self, doc_id: str) -> bool:
        """Delete all chunks for a document.

        Args:
            doc_id: Document identifier to remove.

        Returns:
            True if deletion was attempted (may still fail silently).
        """
        if not self.available:
            return False

        try:
            self._collection.delete(where={"doc_id": doc_id})
            log.info("rag.deleted", doc_id=doc_id)
            return True
        except Exception as exc:
            log.error("rag.delete_failed", doc_id=doc_id, error=str(exc))
            return False

    def count(self) -> int:
        """Return total number of chunks in the collection."""
        if not self.available:
            return 0
        return self._collection.count()


# ──────────────────────────────────────────────
# Singleton Accessors
# ──────────────────────────────────────────────

_pipelines: dict[str, RAGPipeline] = {}


def get_rag_pipeline(
    collection: str = COLLECTION_MARKET_RESEARCH,
) -> RAGPipeline:
    """Get or create a RAG pipeline for the given collection."""
    if collection not in _pipelines:
        _pipelines[collection] = RAGPipeline(collection_name=collection)
    return _pipelines[collection]
