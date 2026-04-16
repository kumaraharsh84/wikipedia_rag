"""
Unit tests for individual RAG pipeline stages.

Each module is tested in isolation. External dependencies (embedding model,
Wikipedia API, LLM) are mocked so the suite runs fast without GPU or network.
"""

import importlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── text_cleaner ──────────────────────────────────────────────────────────────

class TestCleanWikipediaText:

    def test_strips_numeric_citation_markers(self):
        from utils.text_cleaner import clean_wikipedia_text
        result = clean_wikipedia_text("Quantum mechanics[1] was developed[23] in the 1920s.")
        assert "[1]" not in result
        assert "[23]" not in result

    def test_strips_section_headers(self):
        from utils.text_cleaner import clean_wikipedia_text
        result = clean_wikipedia_text("== History ==\nSome text here.")
        assert "==" not in result
        assert "Some text here." in result

    def test_strips_bare_urls(self):
        from utils.text_cleaner import clean_wikipedia_text
        result = clean_wikipedia_text("See https://en.wikipedia.org/wiki/AI for details.")
        assert "https://" not in result

    def test_collapses_multiple_spaces(self):
        from utils.text_cleaner import clean_wikipedia_text
        result = clean_wikipedia_text("Hello   world   foo")
        assert "  " not in result

    def test_empty_string_returns_empty(self):
        from utils.text_cleaner import clean_wikipedia_text
        assert clean_wikipedia_text("") == ""

    def test_preserves_sentence_content(self):
        from utils.text_cleaner import clean_wikipedia_text
        result = clean_wikipedia_text("The Eiffel Tower is 330 metres tall.")
        assert "Eiffel Tower" in result
        assert "330" in result


class TestSplitIntoPassages:

    def test_overlap_shares_sentences_between_passages(self):
        """Overlap=1 means the last sentence of passage N is the first of passage N+1."""
        from utils.text_cleaner import split_into_passages
        # 6 distinct sentences → with window=3, overlap=1, step=2 → starts 0, 2, 4
        sentences = [f"This is sentence {i} in the document." for i in range(6)]
        text = " ".join(sentences)
        passages = split_into_passages(text, max_sentences=3, overlap=1)
        assert len(passages) >= 2
        # sentence 2 should appear in both passage 0 and passage 1
        assert "sentence 2" in passages[0]
        assert "sentence 2" in passages[1]

    def test_min_sentences_filter_drops_short_tail(self):
        """A trailing chunk shorter than min_sentences should be discarded."""
        from utils.text_cleaner import split_into_passages
        # 3 sentences with window=3 → one full chunk, no trailing partial
        sentences = [f"Sentence {i}." for i in range(3)]
        passages = split_into_passages(" ".join(sentences), max_sentences=3, overlap=0, min_sentences=3)
        assert len(passages) == 1

    def test_single_short_sentence_returns_empty(self):
        from utils.text_cleaner import split_into_passages
        assert split_into_passages("Hi.", min_sentences=2) == []

    def test_empty_text_returns_empty(self):
        from utils.text_cleaner import split_into_passages
        assert split_into_passages("") == []

    def test_passages_contain_original_words(self):
        from utils.text_cleaner import split_into_passages
        text = "The mitochondria is the powerhouse of the cell. It generates ATP. This process is called cellular respiration."
        passages = split_into_passages(text, max_sentences=3, overlap=0, min_sentences=1)
        combined = " ".join(passages)
        assert "mitochondria" in combined
        assert "ATP" in combined


# ── search.py — cache key and FIFO eviction ───────────────────────────────────

class TestMakeCacheKey:

    def test_same_passages_produce_same_key(self):
        from backend.search import SemanticSearchEngine
        passages = ["First passage here.", "Second passage here."]
        assert SemanticSearchEngine._make_cache_key(passages) == SemanticSearchEngine._make_cache_key(passages)

    def test_different_passages_produce_different_keys(self):
        from backend.search import SemanticSearchEngine
        k1 = SemanticSearchEngine._make_cache_key(["Hello world."])
        k2 = SemanticSearchEngine._make_cache_key(["Goodbye world."])
        assert k1 != k2

    def test_key_length_is_16_hex_chars(self):
        from backend.search import SemanticSearchEngine
        key = SemanticSearchEngine._make_cache_key(["Any passage."])
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_key_stable_across_calls(self):
        from backend.search import SemanticSearchEngine
        passages = ["Stability test passage."]
        keys = {SemanticSearchEngine._make_cache_key(passages) for _ in range(10)}
        assert len(keys) == 1  # all identical


class TestMemoryCacheFIFOEviction:

    def test_oldest_entry_evicted_when_cache_full(self):
        from backend.search import SemanticSearchEngine
        engine = SemanticSearchEngine(cache_size=2)
        engine._store_in_memory("alpha", MagicMock())
        engine._store_in_memory("beta",  MagicMock())
        assert "alpha" in engine._cache
        engine._store_in_memory("gamma", MagicMock())  # triggers eviction
        assert "alpha" not in engine._cache            # FIFO: oldest removed
        assert "beta"  in engine._cache
        assert "gamma" in engine._cache

    def test_cache_does_not_exceed_max_size(self):
        from backend.search import SemanticSearchEngine
        engine = SemanticSearchEngine(cache_size=3)
        for i in range(10):
            engine._store_in_memory(f"key{i}", MagicMock())
        assert len(engine._cache) <= 3


# ── reranker.py — disabled path and empty input ───────────────────────────────

class TestRerankerFallbacks:

    def test_returns_original_when_model_unavailable(self):
        from backend.reranker import Reranker
        from backend.search import SearchResult
        results = [
            SearchResult(passage="P1", score=0.9, rank=1, source={"title": "T", "url": "u"}),
            SearchResult(passage="P2", score=0.5, rank=2, source={"title": "T", "url": "u"}),
        ]
        r = Reranker()
        # Patch _load so it doesn't reload the singleton model, then clear it
        with patch.object(r, "_load"):
            r._model = None
            assert r.rerank("query", results) == results

    def test_empty_results_returned_unchanged(self):
        from backend.reranker import Reranker
        r = Reranker()
        r._model = None
        assert r.rerank("query", []) == []

    def test_rerank_scores_update_when_model_present(self):
        from backend.reranker import Reranker
        from backend.search import SearchResult
        results = [
            SearchResult(passage="High relevance passage.", score=0.3, rank=1,
                         source={"title": "T", "url": "u"}),
            SearchResult(passage="Low relevance passage.", score=0.9, rank=2,
                         source={"title": "T", "url": "u"}),
        ]
        mock_model = MagicMock()
        # Cross-encoder assigns reverse scores: first passage gets higher score
        mock_model.predict.return_value = np.array([0.95, 0.1])
        r = Reranker()
        r._model = mock_model
        reranked = r.rerank("query", results)
        assert reranked[0].passage == "High relevance passage."
        assert reranked[0].score == pytest.approx(0.95)


# ── source diversity (custom design decision) ─────────────────────────────────

class TestSourceDiversity:
    """
    enforce_source_diversity() is a custom post-ranking step that guarantees
    at least one passage from each fetched Wikipedia article appears in the
    final top-k. Without it, the cross-encoder can fill all slots from one
    high-relevance article and silently drop context from other fetched sources.
    """

    def test_minority_source_promoted_into_top_k(self):
        from backend.reranker import enforce_source_diversity
        from backend.search import SearchResult

        # All top scores from Article A; one passage from Article B with lower score
        results = [
            SearchResult(passage="A1", score=0.9, rank=1, source={"title": "Article A", "url": "urlA"}),
            SearchResult(passage="A2", score=0.8, rank=2, source={"title": "Article A", "url": "urlA"}),
            SearchResult(passage="A3", score=0.7, rank=3, source={"title": "Article A", "url": "urlA"}),
            SearchResult(passage="B1", score=0.4, rank=4, source={"title": "Article B", "url": "urlB"}),
        ]
        out = enforce_source_diversity(results, top_k=3)
        titles = {r.source["title"] for r in out}
        assert "Article B" in titles, "Minority source should be promoted to guarantee diversity"
        assert len(out) == 3

    def test_single_source_not_affected(self):
        from backend.reranker import enforce_source_diversity
        from backend.search import SearchResult

        results = [
            SearchResult(passage="A1", score=0.9, rank=1, source={"title": "Only", "url": "u"}),
            SearchResult(passage="A2", score=0.7, rank=2, source={"title": "Only", "url": "u"}),
        ]
        out = enforce_source_diversity(results, top_k=2)
        assert len(out) == 2
        assert out[0].passage == "A1"  # order preserved

    def test_output_never_exceeds_top_k(self):
        from backend.reranker import enforce_source_diversity
        from backend.search import SearchResult

        results = [
            SearchResult(passage=f"P{i}", score=1.0 - i * 0.1, rank=i,
                         source={"title": f"Src{i % 3}", "url": "u"})
            for i in range(9)
        ]
        out = enforce_source_diversity(results, top_k=5)
        assert len(out) <= 5

    def test_output_sorted_by_score_descending(self):
        from backend.reranker import enforce_source_diversity
        from backend.search import SearchResult

        results = [
            SearchResult(passage="A", score=0.8, rank=1, source={"title": "X", "url": "u"}),
            SearchResult(passage="B", score=0.6, rank=2, source={"title": "Y", "url": "u"}),
            SearchResult(passage="C", score=0.4, rank=3, source={"title": "X", "url": "u"}),
        ]
        out = enforce_source_diversity(results, top_k=3)
        scores = [r.score for r in out]
        assert scores == sorted(scores, reverse=True)
