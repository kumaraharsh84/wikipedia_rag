"""
Wikipedia API wrapper — multi-article fetch with related topics.

Fetches up to `num_articles` Wikipedia articles per query, merges their
passages into a single pool, and tracks which passage came from which
article. Also returns related topic links from the primary article.
"""

from __future__ import annotations

import wikipedia
from typing import List, Tuple, Dict

from utils.logger import get_logger
from utils.text_cleaner import clean_wikipedia_text, split_into_passages

logger = get_logger(__name__)

wikipedia.set_lang("en")

# How many related Wikipedia links to surface in the response
MAX_RELATED = 6


class WikipediaFetcher:
    """Fetches and preprocesses one or more Wikipedia articles per query."""

    def fetch(
        self,
        query: str,
        num_articles: int = 2,
        max_passages_per_article: int = 25,
    ) -> Tuple[List[str], List[Dict], List[str], str, str]:
        """
        Search Wikipedia, fetch the top `num_articles` results, and return
        their merged passages with per-passage source metadata.

        Returns:
            passages:       Flat list of text chunks across all fetched articles.
            sources:        Parallel list — each entry is {"title": ..., "url": ...}
                            for the article that passage came from.
            related_topics: Up to MAX_RELATED related article titles (from primary).
            primary_title:  Title of the first / best-matching article.
            primary_url:    URL of the first / best-matching article.
        """
        logger.info("Fetching %d Wikipedia article(s) for: '%s'", num_articles, query)

        search_results = wikipedia.search(query, results=max(num_articles * 2, 6))
        if not search_results:
            raise ValueError(f"No Wikipedia results found for: '{query}'")

        pages = self._load_pages(search_results, num_articles)
        if not pages:
            raise ValueError(f"Could not load any Wikipedia articles for: '{query}'")

        all_passages: List[str] = []
        all_sources: List[Dict] = []
        related_topics: List[str] = []
        primary_title = pages[0].title
        primary_url   = pages[0].url

        for i, page in enumerate(pages):
            cleaned   = clean_wikipedia_text(page.content)
            passages  = split_into_passages(cleaned)[:max_passages_per_article]
            source    = {"title": page.title, "url": page.url}

            all_passages.extend(passages)
            all_sources.extend([source] * len(passages))

            # Collect related topics from the primary article only
            if i == 0:
                related_topics = self._related_topics(page, query)

            logger.info(
                "  [%d/%d] '%s' — %d passages", i + 1, len(pages), page.title, len(passages)
            )

        logger.info(
            "Total: %d passages from %d article(s)", len(all_passages), len(pages)
        )
        return all_passages, all_sources, related_topics, primary_title, primary_url

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_pages(self, candidates: List[str], limit: int) -> list:
        """
        Try candidate titles in order; return up to `limit` successfully
        loaded pages. Skips disambiguation pages gracefully.
        """
        pages = []
        seen_titles: set = set()

        for title in candidates:
            if len(pages) >= limit:
                break
            try:
                page = wikipedia.page(title, auto_suggest=False)
                norm = page.title.lower()
                if norm not in seen_titles:
                    pages.append(page)
                    seen_titles.add(norm)
            except wikipedia.exceptions.DisambiguationError as exc:
                # Try the first non-ambiguous suggestion
                try:
                    page = wikipedia.page(exc.options[0], auto_suggest=False)
                    norm = page.title.lower()
                    if norm not in seen_titles:
                        pages.append(page)
                        seen_titles.add(norm)
                except Exception:
                    continue
            except wikipedia.exceptions.PageError:
                continue
            except Exception as exc:
                logger.warning("Unexpected error loading '%s': %s", title, exc)
                continue

        return pages

    def _related_topics(self, page, query: str) -> List[str]:
        """
        Return up to MAX_RELATED linked article titles from the primary page,
        filtering out the page itself and very short titles.
        """
        query_words = set(query.lower().split())
        links = getattr(page, "links", []) or []

        # Prefer links whose title shares words with the query
        scored = []
        for link in links:
            if link.lower() == page.title.lower():
                continue
            if len(link) < 4:
                continue
            overlap = len(query_words & set(link.lower().split()))
            scored.append((overlap, link))

        scored.sort(key=lambda x: -x[0])
        return [title for _, title in scored[:MAX_RELATED]]
