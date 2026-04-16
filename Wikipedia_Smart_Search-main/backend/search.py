"""
FAISS-backed semantic search with persistent index and per-passage source tracking.

Index lifecycle
───────────────
1. On first query for an article, build the FAISS index and save it to disk.
2. On subsequent queries, load the saved index — no re-encoding needed.
3. A FIFO in-memory cache avoids repeated disk I/O within a session.

Source tracking
───────────────
Each passage carries a source dict {"title": ..., "url": ...} so the frontend
can show which Wikipedia article each passage came from.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import faiss
import numpy as np

from backend.embeddings import EmbeddingModel
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Vector store selection
# ---------------------------------------------------------------------------

VECTOR_STORE      = os.getenv("VECTOR_STORE", "faiss").lower()   # faiss | pinecone
PINECONE_API_KEY  = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX    = os.getenv("PINECONE_INDEX", "wiki-qa")


class PineconeSearchEngine:
    """
    Drop-in replacement for SemanticSearchEngine that uses Pinecone serverless.

    Usage:
      VECTOR_STORE=pinecone
      PINECONE_API_KEY=your-key
      PINECONE_INDEX=wiki-qa   (index must already exist in Pinecone console)
    """

    def __init__(self) -> None:
        self.model = EmbeddingModel()
        self._pc = None
        self._index = None
        self._load()

    def _load(self) -> None:
        try:
            from pinecone import Pinecone
            self._pc = Pinecone(api_key=PINECONE_API_KEY)
            self._index = self._pc.Index(PINECONE_INDEX)
            logger.info("Pinecone index '%s' connected", PINECONE_INDEX)
        except Exception as exc:
            logger.warning("Pinecone unavailable, falling back to FAISS: %s", exc)
            self._index = None

    def index_article(self, passages: List[str], sources: List[Dict]) -> "PineconeNamespace":
        """Upsert passages into Pinecone and return a handle for searching."""
        if self._index is None:
            raise RuntimeError("Pinecone not available")

        embeddings = self.model.encode(passages)
        namespace = hashlib.md5("".join(passages[:5]).encode()).hexdigest()[:16]

        vectors = [
            {
                "id": f"{namespace}_{i}",
                "values": embeddings[i].tolist(),
                "metadata": {"text": passages[i], "title": sources[i]["title"], "url": sources[i]["url"]},
            }
            for i in range(len(passages))
        ]
        self._index.upsert(vectors=vectors, namespace=namespace)
        return PineconeNamespace(namespace=namespace, index=self._index, sources=sources)

    def search(self, query: str, article_index: "PineconeNamespace", top_k: int = 5) -> List[SearchResult]:
        query_vec = self.model.encode([query])[0].tolist()
        response = article_index.index.query(
            namespace=article_index.namespace,
            vector=query_vec,
            top_k=top_k,
            include_metadata=True,
        )
        results = []
        for rank, match in enumerate(response.matches, start=1):
            m = match.metadata
            results.append(SearchResult(
                passage=m["text"],
                score=float(match.score),
                rank=rank,
                source={"title": m["title"], "url": m["url"]},
            ))
        return results


@dataclass
class PineconeNamespace:
    namespace: str
    index: object
    sources: List[Dict]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    passage: str
    score: float
    rank: int
    source: Dict  # {"title": ..., "url": ...}


@dataclass
class ArticleIndex:
    """FAISS index for one or more Wikipedia articles (merged passages)."""

    cache_key: str           # Used for filenames on disk
    passages: List[str]
    sources: List[Dict]      # Parallel to passages
    _index: Optional[faiss.IndexFlatIP] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, model: EmbeddingModel) -> None:
        """Encode all passages and populate the FAISS index."""
        logger.info("Building FAISS index (%d passages)…", len(self.passages))
        vecs = model.encode(self.passages)
        dim = vecs.shape[1]
        index = faiss.IndexFlatIP(dim)   # Exact cosine (vectors are L2-normalised)
        index.add(vecs)
        self._index = index
        self._save()
        logger.info("FAISS index built and saved (dim=%d, n=%d)", dim, index.ntotal)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[SearchResult]:
        if self._index is None:
            raise RuntimeError("Index not ready — call build() first.")

        scores, indices = self._index.search(query_vec.reshape(1, -1), top_k)
        results: List[SearchResult] = []
        for rank, (idx, score) in enumerate(zip(indices[0], scores[0]), start=1):
            if idx == -1:
                continue
            results.append(SearchResult(
                passage=self.passages[idx],
                score=float(score),
                rank=rank,
                source=self.sources[idx],
            ))
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _faiss_path(self) -> Path:
        return DATA_DIR / f"index_{self.cache_key}.faiss"

    def _meta_path(self) -> Path:
        return DATA_DIR / f"meta_{self.cache_key}.pkl"

    def _save(self) -> None:
        faiss.write_index(self._index, str(self._faiss_path()))
        with open(self._meta_path(), "wb") as f:
            pickle.dump(
                {"cache_key": self.cache_key, "passages": self.passages, "sources": self.sources},
                f,
            )
        logger.debug("Saved index to disk: %s", self._faiss_path())

    @classmethod
    def load_from_disk(cls, cache_key: str) -> Optional["ArticleIndex"]:
        """Return a pre-built ArticleIndex from disk, or None if not found."""
        faiss_path = DATA_DIR / f"index_{cache_key}.faiss"
        meta_path  = DATA_DIR / f"meta_{cache_key}.pkl"

        if not faiss_path.exists() or not meta_path.exists():
            return None

        try:
            index = faiss.read_index(str(faiss_path))
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)
            obj = cls(**meta)
            obj._index = index
            logger.info("Loaded FAISS index from disk: %s", cache_key)
            return obj
        except Exception as exc:
            logger.warning("Failed to load index from disk (%s): %s", cache_key, exc)
            return None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SemanticSearchEngine:
    """Manages building, caching, and searching FAISS indices."""

    def __init__(self, cache_size: int = 20) -> None:
        self.model = EmbeddingModel()
        self._cache: Dict[str, ArticleIndex] = {}   # In-memory FIFO cache
        self._cache_size = cache_size

    # ------------------------------------------------------------------

    @staticmethod
    def _make_cache_key(passages: List[str]) -> str:
        """Stable hash of passage content — same articles → same key."""
        digest = hashlib.md5("".join(passages[:5]).encode()).hexdigest()[:16]
        return digest

    def index_article(
        self,
        passages: List[str],
        sources: List[Dict],
    ) -> ArticleIndex:
        """
        Return an ArticleIndex for the given passages.
        Order of preference: memory cache → disk → build fresh.
        """
        cache_key = self._make_cache_key(passages)

        # 1. Memory cache hit
        if cache_key in self._cache:
            logger.info("Memory cache hit for key %s", cache_key)
            return self._cache[cache_key]

        # 2. Disk cache hit
        on_disk = ArticleIndex.load_from_disk(cache_key)
        if on_disk is not None:
            self._store_in_memory(cache_key, on_disk)
            return on_disk

        # 3. Build fresh
        article_index = ArticleIndex(cache_key=cache_key, passages=passages, sources=sources)
        article_index.build(self.model)
        self._store_in_memory(cache_key, article_index)
        return article_index

    def search(
        self,
        query: str,
        article_index: ArticleIndex,
        top_k: int = 5,
    ) -> List[SearchResult]:
        query_vec = self.model.encode([query])
        return article_index.search(query_vec, top_k=top_k)

    # ------------------------------------------------------------------

    def _store_in_memory(self, key: str, index: ArticleIndex) -> None:
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            logger.debug("Evicted '%s' from memory cache", oldest)
        self._cache[key] = index
