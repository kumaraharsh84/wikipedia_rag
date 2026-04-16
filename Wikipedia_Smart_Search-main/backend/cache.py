"""
Simple TTL-based in-memory cache for QA responses.

Avoids re-fetching Wikipedia and re-running embeddings for repeated queries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TTL = 3600  # seconds (1 hour)


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Thread-safe dict-based cache with per-entry TTL."""

    def __init__(self, ttl: int = DEFAULT_TTL) -> None:
        self._ttl = ttl
        self._store: Dict[str, _CacheEntry] = {}

    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            logger.debug("Cache entry expired: %s", key)
            return None
        logger.debug("Cache hit: %s", key)
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = _CacheEntry(
            value=value,
            expires_at=time.monotonic() + self._ttl,
        )
        logger.debug("Cache set: %s (TTL=%ds)", key, self._ttl)

    def clear(self) -> None:
        self._store.clear()
        logger.info("Cache cleared")

    def __len__(self) -> int:
        return len(self._store)
