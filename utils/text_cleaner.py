"""
Text cleaning and preprocessing utilities.

Uses NLTK sentence tokenization to split text at sentence boundaries,
preserving context far better than naive word-count windowing.
"""

import re
from typing import List

import nltk

from utils.logger import get_logger

logger = get_logger(__name__)

# Download punkt data once at import time (no-op if already present)
nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)


def clean_wikipedia_text(raw_text: str) -> str:
    """
    Remove common Wikipedia artifacts from raw article text.

    Steps:
      1. Strip citation markers  e.g. [1], [note 2], [citation needed]
      2. Remove section-header markup  == Header ==
      3. Strip URLs
      4. Remove non-printable / control characters
      5. Collapse whitespace
    """
    text = raw_text

    # Citation / reference markers
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[[\w\s]{1,30}\]", "", text)

    # Section headers  (== Header ==) — always on their own line in Wikipedia
    text = re.sub(r"^={2,}.+?={2,}\s*$", "", text, flags=re.MULTILINE)

    # Bare URLs
    text = re.sub(r"https?://\S+", "", text)

    # Non-printable / control characters (keep newlines for sentence splitting)
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_into_passages(
    text: str,
    max_sentences: int = 5,
    overlap: int = 1,
    min_sentences: int = 2,
) -> List[str]:
    """
    Split text into overlapping passages using NLTK sentence boundaries.

    This is far superior to word-count windowing because passages always
    start and end at sentence boundaries — no mid-sentence cuts.

    Args:
        text:          Cleaned article text.
        max_sentences: Max sentences per passage.
        overlap:       Sentences shared between consecutive passages.
        min_sentences: Discard passages shorter than this.

    Returns:
        List of passage strings.
    """
    sentences: List[str] = nltk.sent_tokenize(text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return []

    passages: List[str] = []
    step = max(1, max_sentences - overlap)

    for start in range(0, len(sentences), step):
        chunk = sentences[start : start + max_sentences]
        if len(chunk) < min_sentences:
            break
        passages.append(" ".join(chunk))

    logger.debug(
        "Split %d sentences → %d passages (max=%d, overlap=%d)",
        len(sentences), len(passages), max_sentences, overlap,
    )
    return passages
