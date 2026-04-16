"""
Answer generation — supports multiple LLM providers.

LLM_PROVIDER env var (default: "groq"):
  groq      — Groq Cloud (llama-3.3-70b, FREE tier, requires GROQ_API_KEY)
  local     — google/flan-t5-small (CPU, ~500 MB RAM, no API key needed)
  openai    — OpenAI Chat Completions (requires OPENAI_API_KEY)
  anthropic — Anthropic Messages API (requires ANTHROPIC_API_KEY)

Groq is the recommended default — free, fast, and high quality.
Get a free API key at: https://console.groq.com

Streaming:
  stream_tokens() yields (word, is_done) tuples for SSE endpoints.
  For "local", full answer is generated first then words are yielded.
  For API providers, tokens are streamed natively.
"""

from __future__ import annotations

import os
import re
from typing import Generator, List, Tuple

from backend.search import SearchResult
from utils.logger import get_logger

logger = get_logger(__name__)

LLM_PROVIDER     = os.getenv("LLM_PROVIDER", "groq").lower()   # groq | local | openai | anthropic
GENERATOR_MODEL  = "google/flan-t5-small"
ENABLE_GENERATOR = os.getenv("ENABLE_GENERATOR", "true").lower() == "true"
MAX_NEW_TOKENS   = 256
MAX_CONTEXT_CHARS = 1800

SYSTEM_PROMPT = (
    "You are a knowledgeable assistant. Using ONLY the Wikipedia passages "
    "provided below, write a clear, accurate, and well-structured answer "
    "to the question. Synthesize information from all passages — do not "
    "repeat the same point twice. If the passages do not contain enough "
    "information, say so."
)


class AnswerGenerator:
    """Singleton answer generator — delegates to flan-t5, OpenAI, or Anthropic."""

    _instance: AnswerGenerator | None = None

    def __new__(cls) -> AnswerGenerator:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pipeline = None
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        query: str,
        results: List[SearchResult],
        article_title: str,
        history: List[dict] | None = None,
    ) -> str:
        if not results:
            return "No relevant information was found for your query."
        context = self._build_context(results)
        try:
            if LLM_PROVIDER == "groq":
                return self._groq_answer(query, context, history)
            if LLM_PROVIDER == "openai":
                return self._openai_answer(query, context, history)
            if LLM_PROVIDER == "anthropic":
                return self._anthropic_answer(query, context, history)
        except Exception as exc:
            logger.warning("API provider '%s' failed, falling back to local: %s", LLM_PROVIDER, exc)
        return self._local_answer(query, context, article_title, results)

    def stream_tokens(
        self,
        query: str,
        results: List[SearchResult],
        article_title: str,
        history: List[dict] | None = None,
    ) -> Generator[Tuple[str, bool], None, None]:
        """
        Yield (token_str, is_done) pairs.
        - is_done=False: partial token to append to UI
        - is_done=True:  final sentinel (token_str is empty)
        """
        if not results:
            yield "No relevant information was found for your query.", True
            return

        context = self._build_context(results)
        try:
            if LLM_PROVIDER == "groq":
                yield from self._groq_stream(query, context, history)
                return
            if LLM_PROVIDER == "openai":
                yield from self._openai_stream(query, context, history)
                return
            if LLM_PROVIDER == "anthropic":
                yield from self._anthropic_stream(query, context, history)
                return
        except Exception as exc:
            logger.warning("API streaming failed, falling back to local: %s", exc)

        # Local: generate full answer, then yield word-by-word
        answer = self._local_answer(query, context, article_title, results)
        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == len(words) - 1 else word + " "
            yield chunk, False
        yield "", True

    # ------------------------------------------------------------------
    # Message builder (shared by all API providers)
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        query: str,
        context: str,
        history: List[dict] | None,
    ) -> List[dict]:
        """Build the messages array with optional conversation history."""
        messages: List[dict] = []
        # Inject prior turns (role: user/assistant)
        for turn in (history or []):
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        # Current question with fresh Wikipedia context
        messages.append({
            "role": "user",
            "content": (
                f"Question: {query}\n\n"
                f"Wikipedia Passages:\n{context}\n\n"
                "Answer:"
            ),
        })
        return messages

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def _build_context(self, results: List[SearchResult]) -> str:
        seen_sentences: set = set()
        parts: List[str] = []
        total = 0

        for r in results:
            sentences = re.split(r"(?<=[.!?])\s+", r.passage)
            unique = []
            for s in sentences:
                key = re.sub(r"\s+", " ", s.lower().strip())[:80]
                if key not in seen_sentences:
                    seen_sentences.add(key)
                    unique.append(s)

            chunk = " ".join(unique)
            if not chunk:
                continue
            if total + len(chunk) > MAX_CONTEXT_CHARS:
                remaining = MAX_CONTEXT_CHARS - total
                chunk = chunk[:remaining].rsplit(" ", 1)[0]
                parts.append(f"[{r.source['title']}]: {chunk}")
                break

            parts.append(f"[{r.source['title']}]: {chunk}")
            total += len(chunk)

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Local flan-t5
    # ------------------------------------------------------------------

    def _load_local(self) -> None:
        if self._pipeline is not None or not ENABLE_GENERATOR:
            return
        try:
            import torch
            from transformers import pipeline
            logger.info("Loading generator '%s'…", GENERATOR_MODEL)
            self._pipeline = pipeline(
                "text2text-generation",
                model=GENERATOR_MODEL,
                torch_dtype=torch.float32,
                device=-1,
            )
            logger.info("Generator loaded")
        except Exception as exc:
            logger.warning("Could not load generator: %s", exc)
            self._pipeline = None

    def _local_answer(
        self,
        query: str,
        context: str,
        article_title: str,
        results: List[SearchResult],
    ) -> str:
        self._load_local()
        if self._pipeline is not None:
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"Question: {query}\n\n"
                f"Wikipedia Passages:\n{context}\n\n"
                "Answer:"
            )
            try:
                output = self._pipeline(
                    prompt,
                    max_new_tokens=MAX_NEW_TOKENS,
                    do_sample=False,
                    no_repeat_ngram_size=3,
                )
                generated = output[0]["generated_text"].strip()
                # Capitalise first letter if flan-t5 produces lowercase output
                if generated and generated[0].islower():
                    generated = generated[0].upper() + generated[1:]
                if len(generated) >= 20:
                    return generated
            except Exception as exc:
                logger.warning("flan-t5 generation failed: %s", exc)

        # Extractive fallback — return the best passage text directly
        best = results[0]
        answer = best.passage
        if len(results) > 1:
            extras = []
            for r in results[1:3]:
                snippet = r.passage[:300] + ("…" if len(r.passage) > 300 else "")
                extras.append(snippet)
            if extras:
                answer += "\n\n" + "\n\n".join(extras)
        return answer

    # ------------------------------------------------------------------
    # Groq (FREE — llama-3.3-70b)
    # ------------------------------------------------------------------

    def _groq_answer(self, query: str, context: str, history: List[dict] | None) -> str:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set — get a free key at https://console.groq.com")
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self._build_messages(query, context, history),
            max_tokens=512,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    def _groq_stream(
        self, query: str, context: str, history: List[dict] | None
    ) -> Generator[Tuple[str, bool], None, None]:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set — get a free key at https://console.groq.com")
        client = Groq(api_key=api_key)
        stream = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self._build_messages(query, context, history),
            max_tokens=512,
            temperature=0.3,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta, False
        yield "", True

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    def _openai_answer(self, query: str, context: str, history: List[dict] | None) -> str:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self._build_messages(query, context, history),
            max_tokens=512,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    def _openai_stream(
        self, query: str, context: str, history: List[dict] | None
    ) -> Generator[Tuple[str, bool], None, None]:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        client = OpenAI(api_key=api_key)
        stream = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self._build_messages(query, context, history),
            max_tokens=512,
            temperature=0.3,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta, False
        yield "", True

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _anthropic_answer(self, query: str, context: str, history: List[dict] | None) -> str:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=self._build_messages(query, context, history),
        )
        return msg.content[0].text.strip()

    def _anthropic_stream(
        self, query: str, context: str, history: List[dict] | None
    ) -> Generator[Tuple[str, bool], None, None]:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        client = anthropic.Anthropic(api_key=api_key)
        with client.messages.stream(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=self._build_messages(query, context, history),
        ) as stream:
            for text in stream.text_stream:
                yield text, False
        yield "", True
