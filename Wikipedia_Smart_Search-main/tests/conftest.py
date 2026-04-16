"""
Pytest configuration and shared fixtures.
"""

import sys
import os

# Ensure project root is on the path so backend/utils imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="session")
def client():
    """FastAPI test client shared across the whole test session."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sample_passages():
    return [
        "Artificial intelligence (AI) is intelligence demonstrated by machines.",
        "Machine learning is a subset of AI that enables systems to learn from data.",
        "Deep learning uses neural networks with many layers to model complex patterns.",
        "Natural language processing (NLP) enables computers to understand human language.",
        "Computer vision allows machines to interpret and understand visual information.",
    ]


@pytest.fixture()
def sample_sources(sample_passages):
    return [{"title": "Artificial intelligence", "url": "https://en.wikipedia.org/wiki/Artificial_intelligence"}] * len(sample_passages)
