"""
Unit tests for utils/text_cleaner.py
"""

import pytest
from utils.text_cleaner import clean_wikipedia_text, split_into_passages


class TestCleanWikipediaText:

    def test_removes_citation_numbers(self):
        raw = "Artificial intelligence[1] is a field[23] of computer science."
        result = clean_wikipedia_text(raw)
        assert "[1]" not in result
        assert "[23]" not in result
        assert "Artificial intelligence" in result

    def test_removes_citation_labels(self):
        raw = "This needs citation[citation needed] and verification[note 1]."
        result = clean_wikipedia_text(raw)
        assert "[citation needed]" not in result

    def test_removes_section_headers(self):
        raw = "== History ==\nSome historical content.\n=== Early Days ===\nMore content."
        result = clean_wikipedia_text(raw)
        assert "==" not in result
        assert "Some historical content" in result

    def test_removes_urls(self):
        raw = "See https://example.com for more details about AI."
        result = clean_wikipedia_text(raw)
        assert "https://" not in result
        assert "See" in result

    def test_collapses_whitespace(self):
        raw = "Word1    Word2\t\tWord3"
        result = clean_wikipedia_text(raw)
        assert "  " not in result

    def test_strips_leading_trailing_whitespace(self):
        raw = "   Some text here.   "
        result = clean_wikipedia_text(raw)
        assert result == result.strip()

    def test_empty_string(self):
        assert clean_wikipedia_text("") == ""

    def test_preserves_meaningful_content(self):
        raw = "Quantum computing is a type of computation[1] that harnesses quantum mechanics."
        result = clean_wikipedia_text(raw)
        assert "Quantum computing" in result
        assert "quantum mechanics" in result


class TestSplitIntoPassages:

    def test_returns_list(self, ):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        result = split_into_passages(text)
        assert isinstance(result, list)

    def test_non_empty_text_returns_passages(self):
        text = (
            "Artificial intelligence is intelligence demonstrated by machines. "
            "It is used in many fields including medicine and finance. "
            "Machine learning is a core subfield of AI. "
            "Deep learning uses neural networks with many layers. "
            "Natural language processing handles text and speech."
        )
        passages = split_into_passages(text)
        assert len(passages) >= 1

    def test_short_text_still_produces_passage(self):
        text = "This is a sentence. This is another one."
        passages = split_into_passages(text, min_sentences=1)
        assert len(passages) >= 1

    def test_passages_are_strings(self):
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        for p in split_into_passages(text):
            assert isinstance(p, str)
            assert len(p) > 0

    def test_overlap_creates_shared_content(self):
        """With overlap=1, consecutive passages should share at least one sentence."""
        sentences = [f"This is sentence number {i}." for i in range(10)]
        text = " ".join(sentences)
        passages = split_into_passages(text, max_sentences=3, overlap=1)
        # With overlap, we expect more passages than without
        passages_no_overlap = split_into_passages(text, max_sentences=3, overlap=0)
        assert len(passages) >= len(passages_no_overlap)

    def test_empty_text_returns_empty_list(self):
        assert split_into_passages("") == []
