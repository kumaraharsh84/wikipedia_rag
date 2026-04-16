"""
Cross-encoder re-ranking for improved retrieval precision.

Why two stages?
───────────────
Stage 1 (FAISS bi-encoder): fast approximate retrieval — scores passages
independently of each other using pre-computed embeddings.

Stage 2 (cross-encoder): slow but accurate — encodes (query, passage) pairs
jointly, capturing deeper query-passage interaction. Applied only to the small
FAISS candidate set (top-k), so speed is acceptable.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (~86 MB, CPU-friendly)
"""

from __future__ import annotations

import os
from typing import List

from utils.logger import get_logger
from backend.search import SearchResult

logger = get_logger(__name__)

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
ENABLE_RERANKER = os.getenv("ENABLE_RERANKER", "true").lower() == "true"


class Reranker:
    """Singleton cross-encoder re-ranker."""

    _instance: Reranker | None = None

    def __new__(cls) -> Reranker:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    def _load(self) -> None:
        if self._model is not None:
            return
        if not ENABLE_RERANKER:
            logger.info("Reranker disabled via ENABLE_RERANKER env var")
            return
        try:
            from sentence_transformers import CrossEncoder
            logger.info("Loading cross-encoder '%s'…", CROSS_ENCODER_MODEL)
            self._model = CrossEncoder(CROSS_ENCODER_MODEL, max_length=512)
            logger.info("Cross-encoder loaded")
        except Exception as exc:
            logger.warning("Could not load cross-encoder (will skip re-ranking): %s", exc)
            self._model = None

    def rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """
        Re-score *results* using the cross-encoder and return them sorted
        by cross-encoder score (descending). Falls back gracefully if the
        model is unavailable.
        """
        self._load()

        if self._model is None or not results:
            return results

        pairs = [(query, r.passage) for r in results]
        try:
            scores = self._model.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            logger.warning("Cross-encoder inference failed: %s — returning original order", exc)
            return results

        reranked = sorted(
            zip(results, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        final: List[SearchResult] = []
        for new_rank, (result, score) in enumerate(reranked, start=1):
            final.append(SearchResult(
                passage=result.passage,
                score=float(score),
                rank=new_rank,
                source=result.source,
            ))

        logger.debug("Re-ranked %d results with cross-encoder", len(final))
        return final


def enforce_source_diversity(
    results: List[SearchResult],
    top_k: int,
) -> List[SearchResult]:
    """
    Custom post-ranking step: guarantee at least one passage per unique source
    appears in the final top-k.

    Why this matters
    ────────────────
    When 2–5 Wikipedia articles are fetched, the cross-encoder can legitimately
    assign all top-k slots to one highly-relevant article, silently dropping
    every passage from the other fetched sources.  That's fine for precision
    but bad for breadth — the LLM loses context from potentially useful articles
    and the user sees no evidence that other sources were searched.

    Algorithm
    ─────────
    1. Walk results in score order; reserve the best passage from each source.
    2. Fill remaining slots (top_k − num_sources) with the next-best by score.
    3. Re-sort the final set by score so the UI renders them in relevance order.

    This adds negligible latency (O(n)) and raises answer breadth measurably
    when queries span multiple articles (e.g. "compare X and Y").
    """
    if not results:
        return results

    unique_sources = list(dict.fromkeys(r.source["title"] for r in results))
    if len(unique_sources) <= 1:
        return results[:top_k]

    seen: set = set()
    reserved: List[SearchResult] = []
    remaining: List[SearchResult] = []

    for r in results:
        title = r.source["title"]
        if title not in seen:
            seen.add(title)
            reserved.append(r)
        else:
            remaining.append(r)

    slots_left = max(0, top_k - len(reserved))
    final = reserved + remaining[:slots_left]
    final.sort(key=lambda x: x.score, reverse=True)
    return final[:top_k]
