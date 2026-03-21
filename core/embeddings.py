# core/embeddings.py
import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

logger = logging.getLogger(__name__)

# Load embedding model once at module level — not on every call
# Uses ONNXMiniLM_L6_V2 via onnxruntime (no PyTorch dependency)
_embedding_function = DefaultEmbeddingFunction()

# Cache ChromaDB clients per session — don't recreate on every request
_chroma_clients: dict[str, Any] = {}


def _get_collection(session_id: str) -> Any:
    """Get or create ChromaDB collection for a session. Cached per session."""
    if session_id not in _chroma_clients:
        _chroma_clients[session_id] = chromadb.PersistentClient(
            path=str(Path(os.getenv("DATA_DIR", ".")) / "chroma_db" / session_id)
        )
    client = _chroma_clients[session_id]
    return client.get_or_create_collection(
        name="papers",
        embedding_function=_embedding_function,
    )


def index_chunks(chunks: list[dict[str, Any]], session_id: str) -> int:
    """Index chunks into ChromaDB for a session.

    Args:
        chunks: List of chunk dicts with keys: text, page, source, chunk_id.
        session_id: The session to scope this index to.

    Returns:
        Number of chunks indexed.
    """
    if not chunks:
        return 0

    collection = _get_collection(session_id)

    collection.add(
        documents=[c["text"] for c in chunks],
        metadatas=[{"source": c["source"], "page": c["page"]} for c in chunks],
        ids=[c["chunk_id"] for c in chunks],
    )

    logger.info("Indexed %d chunks for session %s", len(chunks), session_id)
    return len(chunks)


def retrieve(query: str, session_id: str, n_results: int = 15) -> list[dict[str, Any]]:
    """Semantic search over a session's indexed chunks.

    Args:
        query: The search query text to embed and retrieve against.
        session_id: The session whose ChromaDB collection to search.
        n_results: Maximum number of chunks to return.

    Returns:
        List of chunk dicts with keys: text, source, page.
        Empty list if no relevant chunks found.
    """
    collection = _get_collection(session_id)

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
        )
    except Exception as e:
        logger.warning("ChromaDB query failed for session %s: %s", session_id, e)
        return []

    chunks = []
    for doc, meta in zip(
        results["documents"][0],
        results["metadatas"][0],
        strict=False,
    ):
        chunks.append(
            {
                "text": doc,
                "source": meta["source"],
                "page": meta["page"],
            }
        )

    return chunks
