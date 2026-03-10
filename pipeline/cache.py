# pipeline/cache.py
"""
ChromaDB-backed result cache.
- Keyed by SHA-256 of document text — same docs = instant cache hit, zero Nova calls
- Gracefully degrades to no-op if ChromaDB is unavailable or CACHE_ENABLED=false
- Stores/returns DiligenceResult as serialised JSON
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Module-level singletons — initialised once on first use
_client     = None
_collection = None


def _get_collection():
    """
    Lazy-initialise ChromaDB client + collection.
    Returns None (silently) if ChromaDB is unavailable or cache is disabled.
    """
    global _client, _collection

    if not settings.cache_enabled:
        return None

    if _collection is not None:
        return _collection

    try:
        import chromadb

        _client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = _client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB cache initialised at %s", settings.chroma_path)
    except Exception as exc:
        logger.warning("ChromaDB unavailable — caching disabled: %s", exc)
        _collection = None

    return _collection


def doc_hash(text: str) -> str:
    """Stable SHA-256 hash of document content — used as the cache key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_get(key: str) -> Optional[dict]:
    """
    Retrieve a cached pipeline result by document hash.

    Returns:
        Parsed dict if cache hit, None on miss or error.
    """
    col = _get_collection()
    if col is None:
        return None

    try:
        res = col.get(ids=[key], include=["documents"])
        docs = res.get("documents", [])
        if docs and docs[0]:
            logger.info("Cache HIT for key=%s…", key[:12])
            return json.loads(docs[0])
    except Exception as exc:
        logger.warning("Cache get error (key=%s…): %s", key[:12], exc)

    return None


def cache_set(key: str, result: dict) -> None:
    """
    Store a pipeline result dict in ChromaDB.
    Silently swallows errors — cache failures must never break the pipeline.
    """
    col = _get_collection()
    if col is None:
        return

    try:
        col.upsert(
            ids=[key],
            documents=[json.dumps(result)],
            metadatas=[{"hash": key}],
        )
        logger.info("Cache SET for key=%s…", key[:12])
    except Exception as exc:
        logger.warning("Cache set error (key=%s…): %s", key[:12], exc)


def cache_invalidate(key: str) -> None:
    """Explicitly remove a cached entry — useful for forcing a re-run."""
    col = _get_collection()
    if col is None:
        return

    try:
        col.delete(ids=[key])
        logger.info("Cache INVALIDATED for key=%s…", key[:12])
    except Exception as exc:
        logger.warning("Cache invalidate error (key=%s…): %s", key[:12], exc)