"""
Embedding generation using a HuggingFace sentence-transformer model.

The model is loaded once (singleton pattern) to avoid repeated disk I/O.
"""

from __future__ import annotations

from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from utils.logger import get_logger

logger = get_logger(__name__)

# Lightweight but accurate model; ~90 MB download on first run
MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingModel:
    """Singleton wrapper around a SentenceTransformer model."""

    _instance: EmbeddingModel | None = None

    def __new__(cls) -> EmbeddingModel:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._model is None:
            logger.info("Loading embedding model '%s' …", MODEL_NAME)
            self._model = SentenceTransformer(MODEL_NAME)
            logger.info("Model loaded (dim=%d)", self.dim)

    # ------------------------------------------------------------------

    @property
    def dim(self) -> int:
        self._load()
        return self._model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Encode *texts* into L2-normalised float32 vectors.

        Returns shape (len(texts), dim).
        """
        self._load()
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,   # Unit vectors → cosine ≡ dot product
            convert_to_numpy=True,
        )
        return vectors.astype(np.float32)
