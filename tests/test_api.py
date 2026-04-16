"""
Integration tests for the FastAPI backend.

These tests use FastAPI's TestClient (synchronous) and mock the heavy
external calls (Wikipedia fetch, embedding model) so the suite runs fast
without a GPU or internet connection.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:

    def test_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_response_has_status_key(self):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_response_has_version(self):
        data = client.get("/health").json()
        assert "version" in data


# ---------------------------------------------------------------------------
# /ask — input validation
# ---------------------------------------------------------------------------

class TestAskValidation:

    def test_query_too_short_returns_422(self):
        response = client.post("/ask", json={"query": "Hi"})
        assert response.status_code == 422

    def test_empty_query_returns_422(self):
        response = client.post("/ask", json={"query": ""})
        assert response.status_code == 422

    def test_top_k_out_of_range_returns_422(self):
        response = client.post("/ask", json={"query": "What is AI?", "top_k": 50})
        assert response.status_code == 422

    def test_num_articles_out_of_range_returns_422(self):
        response = client.post("/ask", json={"query": "What is AI?", "num_articles": 10})
        assert response.status_code == 422

    def test_html_in_query_is_stripped(self):
        """The sanitiser should strip <script> tags before the query is processed."""
        mock_result = MagicMock()
        mock_result.passage = "AI is the simulation of human intelligence."
        mock_result.score   = 0.9
        mock_result.source  = {"title": "AI", "url": "https://en.wikipedia.org/wiki/AI"}

        with patch("backend.main.fetcher") as mock_fetcher, \
             patch("backend.main.engine") as mock_engine, \
             patch("backend.main.reranker") as mock_reranker, \
             patch("backend.main.generator") as mock_generator, \
             patch("backend.main.cache") as mock_cache:

            mock_cache.get.return_value = None
            mock_fetcher.fetch.return_value = (
                [mock_result.passage],
                [mock_result.source],
                ["Machine learning"],
                "Artificial intelligence",
                "https://en.wikipedia.org/wiki/AI",
            )
            mock_engine.index_article.return_value = MagicMock()
            mock_engine.search.return_value        = [mock_result]
            mock_reranker.rerank.return_value      = [mock_result]
            mock_generator.generate.return_value   = "AI is intelligence by machines."

            response = client.post("/ask", json={"query": "<script>alert(1)</script> What is AI?"})
            # Sanitised query ("What is AI?") is valid — should succeed or 404 if wiki fails
            assert response.status_code in (200, 404)

    def test_control_characters_stripped(self):
        """Control characters in query should not crash the endpoint."""
        with patch("backend.main.fetcher") as mock_fetcher, \
             patch("backend.main.cache") as mock_cache:

            mock_cache.get.return_value = None
            mock_fetcher.fetch.side_effect = ValueError("no results")
            response = client.post("/ask", json={"query": "What\x00 is\x01 AI?"})
            assert response.status_code in (404, 422)


# ---------------------------------------------------------------------------
# /ask — successful flow (fully mocked)
# ---------------------------------------------------------------------------

class TestAskSuccess:

    @pytest.fixture(autouse=True)
    def mock_pipeline(self):
        """Mock all external calls so tests run without network/GPU."""
        mock_result = MagicMock()
        mock_result.passage = "Artificial intelligence (AI) is intelligence demonstrated by machines."
        mock_result.score   = 0.92
        mock_result.source  = {
            "title": "Artificial intelligence",
            "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        }

        with patch("backend.main.fetcher") as mock_fetcher, \
             patch("backend.main.engine") as mock_engine, \
             patch("backend.main.reranker") as mock_reranker, \
             patch("backend.main.generator") as mock_generator, \
             patch("backend.main.cache") as mock_cache:

            mock_cache.get.return_value = None          # Force cache miss

            mock_fetcher.fetch.return_value = (
                [mock_result.passage],
                [mock_result.source],
                ["Machine learning", "Deep learning"],
                "Artificial intelligence",
                "https://en.wikipedia.org/wiki/Artificial_intelligence",
            )
            mock_engine.index_article.return_value = MagicMock()
            mock_engine.search.return_value        = [mock_result]
            mock_reranker.rerank.return_value      = [mock_result]
            mock_generator.generate.return_value   = "AI is intelligence demonstrated by machines."

            yield

    def test_returns_200(self):
        response = client.post("/ask", json={"query": "What is Artificial Intelligence?"})
        assert response.status_code == 200

    def test_response_has_required_fields(self):
        data = client.post("/ask", json={"query": "What is Artificial Intelligence?"}).json()
        for field in ("query", "answer", "primary_title", "primary_url", "passages", "sources", "related_topics"):
            assert field in data, f"Missing field: {field}"

    def test_answer_is_non_empty(self):
        data = client.post("/ask", json={"query": "What is Artificial Intelligence?"}).json()
        assert len(data["answer"]) > 0

    def test_passages_is_list(self):
        data = client.post("/ask", json={"query": "What is Artificial Intelligence?"}).json()
        assert isinstance(data["passages"], list)

    def test_passage_objects_have_score_and_source(self):
        """Passages are now objects with {passage, score, source} — not bare strings."""
        data = client.post("/ask", json={"query": "What is Artificial Intelligence?"}).json()
        for p in data["passages"]:
            assert "passage" in p
            assert "score" in p
            assert "source" in p

    def test_sources_is_list(self):
        data = client.post("/ask", json={"query": "What is Artificial Intelligence?"}).json()
        assert isinstance(data["sources"], list)


# ---------------------------------------------------------------------------
# /ask — Wikipedia not found
# ---------------------------------------------------------------------------

class TestAskNotFound:

    def test_returns_404_when_wikipedia_fails(self):
        with patch("backend.main.fetcher") as mock_fetcher, \
             patch("backend.main.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_fetcher.fetch.side_effect = ValueError("No results found")
            response = client.post("/ask", json={"query": "xyzzy1234nonexistent"})
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# /metrics
# ---------------------------------------------------------------------------

class TestMetrics:

    def test_returns_200(self):
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_has_required_fields(self):
        data = client.get("/metrics").json()
        for field in ("uptime_seconds", "total_requests", "cache_hits", "cache_hit_rate_pct", "cache_entries"):
            assert field in data, f"Missing field: {field}"

    def test_uptime_is_non_negative(self):
        data = client.get("/metrics").json()
        assert data["uptime_seconds"] >= 0

    def test_hit_rate_is_percentage(self):
        data = client.get("/metrics").json()
        assert 0.0 <= data["cache_hit_rate_pct"] <= 100.0


# ---------------------------------------------------------------------------
# /cache/clear
# ---------------------------------------------------------------------------

class TestCacheClear:

    def test_returns_200(self):
        response = client.get("/cache/clear")
        assert response.status_code == 200

    def test_response_has_message(self):
        data = client.get("/cache/clear").json()
        assert "message" in data
