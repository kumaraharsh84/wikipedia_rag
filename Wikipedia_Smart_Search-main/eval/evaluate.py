"""
Offline evaluation script for the Wikipedia Smart QA system.

Metrics computed
────────────────
  Precision@k     — fraction of top-k passages whose text overlaps with
                    the expected answer keywords (keyword recall proxy)
  MRR@k           — Mean Reciprocal Rank of first relevant passage
  Avg latency     — mean wall-clock time per query (ms)
  p50 / p95 / p99 — latency percentiles
  Cache hit rate  — fraction of queries served from cache

Usage
─────
  # Run against a live backend
  python eval/evaluate.py --url http://localhost:8000

  # Run with custom benchmark file
  python eval/evaluate.py --url http://localhost:8000 --bench eval/bench.json

  # Save results to JSON
  python eval/evaluate.py --url http://localhost:8000 --out eval/results.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

# ---------------------------------------------------------------------------
# Default benchmark queries (query → expected keywords in a good answer)
# ---------------------------------------------------------------------------

DEFAULT_BENCH: List[Dict] = [
    {
        "query": "What is Artificial Intelligence?",
        "keywords": ["intelligence", "machine", "learning", "computer"],
    },
    {
        "query": "Explain Quantum Computing",
        "keywords": ["qubit", "quantum", "superposition", "computing"],
    },
    {
        "query": "What is Machine Learning?",
        "keywords": ["data", "algorithm", "model", "training"],
    },
    {
        "query": "History of the Internet",
        "keywords": ["ARPANET", "network", "protocol", "web"],
    },
    {
        "query": "How does CRISPR gene editing work?",
        "keywords": ["DNA", "gene", "protein", "genome"],
    },
    {
        "query": "Explain the Theory of Relativity",
        "keywords": ["Einstein", "space", "time", "energy"],
    },
    {
        "query": "Who was Nikola Tesla?",
        "keywords": ["electricity", "inventor", "current", "coil"],
    },
    {
        "query": "What causes climate change?",
        "keywords": ["greenhouse", "carbon", "temperature", "emissions"],
    },
]


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def precision_at_k(passages: List[str], keywords: List[str], k: int) -> float:
    """
    Fraction of top-k passages that contain at least one expected keyword.
    This is a keyword-recall proxy — not ground-truth precision.
    """
    top = passages[:k]
    if not top:
        return 0.0
    hits = sum(
        1 for p in top
        if any(kw.lower() in p.lower() for kw in keywords)
    )
    return hits / len(top)


def mrr_at_k(passages: List[str], keywords: List[str], k: int) -> float:
    """Mean Reciprocal Rank — 1/rank of the first relevant passage."""
    for rank, passage in enumerate(passages[:k], start=1):
        if any(kw.lower() in passage.lower() for kw in keywords):
            return 1.0 / rank
    return 0.0


def percentile(values: List[float], p: int) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def judge_faithfulness(
    answer: str,
    passages: List[str],
    query: str,
) -> Optional[float]:
    """
    LLM-as-judge: asks the LLM whether the generated answer is grounded in
    the retrieved passages, or whether it introduces claims not found in them.

    Returns 1.0 (faithful / YES), 0.0 (unfaithful / NO), or None if the
    judge could not run (missing API key, network error, etc.).

    This measures *generation* quality — the complement of Precision@k which
    measures *retrieval* quality. Production RAG systems (Cohere, Weaviate,
    Ragas) expose this metric under names like "faithfulness" or "groundedness".

    Why LLM-as-judge?
    - Keyword overlap can't detect fabricated but plausible-sounding claims
    - A judge that reads both answer and passages catches subtler hallucinations
    - Using the same LLM family as the generator is an established baseline
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None  # Silently skip — don't crash the benchmark

    passages_str = "\n\n".join(
        f"[Passage {i + 1}]: {p[:400]}" for i, p in enumerate(passages[:5])
    )
    judge_prompt = (
        f"Question: {query}\n\n"
        f"Retrieved passages:\n{passages_str}\n\n"
        f"Generated answer: {answer[:600]}\n\n"
        "Task: Using ONLY the retrieved passages above as your reference, "
        "decide whether the generated answer is factually supported.\n"
        "Reply YES if every factual claim in the answer can be traced back "
        "to the retrieved passages.\n"
        "Reply NO if the answer contains facts, numbers, or claims that are "
        "absent from or contradicted by the retrieved passages.\n"
        "Your first word must be YES or NO."
    )
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "user", "content": judge_prompt}],
            max_tokens=16,
            temperature=0.0,
        )
        verdict = resp.choices[0].message.content.strip().upper()
        return 1.0 if verdict.startswith("YES") else 0.0
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_evaluation(
    base_url: str,
    bench: List[Dict],
    top_k: int = 5,
    api_key: str = "",
    faithfulness: bool = True,
) -> Dict:
    headers = {"X-API-Key": api_key} if api_key else {}
    latencies: List[float] = []
    p_at_k_scores: List[float] = []
    mrr_scores: List[float] = []
    faithfulness_scores: List[float] = []
    cache_hits = 0
    errors = 0
    per_query = []

    has_groq = bool(os.getenv("GROQ_API_KEY"))
    run_faithfulness = faithfulness and has_groq

    print(f"\nRunning {len(bench)} benchmark queries against {base_url}\n")
    if run_faithfulness:
        print("Faithfulness scoring: ENABLED (LLM-as-judge via Groq)")
    else:
        print("Faithfulness scoring: DISABLED (set GROQ_API_KEY to enable)")
    print()
    print(f"{'Query':<45} {'P@k':>6} {'MRR':>6} {'Faith':>6} {'Latency':>10}")
    print("-" * 82)

    for item in bench:
        query = item["query"]
        keywords = item["keywords"]

        t0 = time.time()
        try:
            resp = requests.post(
                f"{base_url}/ask",
                json={"query": query, "top_k": top_k},
                headers=headers,
                timeout=120,
            )
            elapsed_ms = (time.time() - t0) * 1000

            if resp.status_code != 200:
                errors += 1
                print(f"  ERROR {resp.status_code}: {query[:40]}")
                continue

            data = resp.json()
            passage_objects = data.get("passages", [])
            # passages may be plain strings or passage objects
            passages = [
                p["passage"] if isinstance(p, dict) else p
                for p in passage_objects
            ]
            answer = data.get("answer", "")
            cached = data.get("cached", False)

            pk  = precision_at_k(passages, keywords, top_k)
            mrr = mrr_at_k(passages, keywords, top_k)

            # Faithfulness: LLM-as-judge (only if enabled and answer exists)
            faith: Optional[float] = None
            if run_faithfulness and answer:
                faith = judge_faithfulness(answer, passages, query)

            latencies.append(elapsed_ms)
            p_at_k_scores.append(pk)
            mrr_scores.append(mrr)
            if faith is not None:
                faithfulness_scores.append(faith)
            if cached:
                cache_hits += 1

            entry: Dict = {
                "query": query,
                "precision_at_k": round(pk, 3),
                "mrr": round(mrr, 3),
                "latency_ms": round(elapsed_ms, 1),
                "cached": cached,
            }
            if faith is not None:
                entry["faithfulness"] = faith

            per_query.append(entry)

            faith_str = f"{faith:.0f}" if faith is not None else "  —"
            print(
                f"  {query[:43]:<45} {pk:>6.3f} {mrr:>6.3f} {faith_str:>6} {elapsed_ms:>8.0f}ms"
            )

        except requests.exceptions.Timeout:
            errors += 1
            print(f"  TIMEOUT: {query[:40]}")
        except Exception as exc:
            errors += 1
            print(f"  ERROR: {query[:40]} — {exc}")

    # Aggregate
    n = len(latencies)
    summary: Dict = {
        "queries_run": len(bench),
        "successful": n,
        "errors": errors,
        "mean_precision_at_k": round(sum(p_at_k_scores) / n, 3) if n else 0,
        "mean_mrr": round(sum(mrr_scores) / n, 3) if n else 0,
        "latency_mean_ms": round(sum(latencies) / n, 1) if n else 0,
        "latency_p50_ms": round(percentile(latencies, 50), 1),
        "latency_p95_ms": round(percentile(latencies, 95), 1),
        "latency_p99_ms": round(percentile(latencies, 99), 1),
        "cache_hit_rate": round(cache_hits / n, 3) if n else 0,
    }
    if faithfulness_scores:
        nf = len(faithfulness_scores)
        summary["mean_faithfulness"] = round(sum(faithfulness_scores) / nf, 3)
        summary["faithfulness_queries"] = nf

    results = {"summary": summary, "per_query": per_query}

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for k, v in results["summary"].items():
        print(f"  {k:<30} {v}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Evaluate Wikipedia Smart QA")
    parser.add_argument("--url",   default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--bench", default=None, help="Path to custom benchmark JSON")
    parser.add_argument("--out",   default=None, help="Save results to this JSON file")
    parser.add_argument("--k",     default=5, type=int, help="Top-k passages")
    parser.add_argument("--api-key", default="", help="API key if auth is enabled")
    parser.add_argument(
        "--no-faithfulness",
        action="store_true",
        help="Disable LLM-as-judge faithfulness scoring (faster, no GROQ_API_KEY needed)",
    )
    args = parser.parse_args()

    bench = DEFAULT_BENCH
    if args.bench:
        with open(args.bench) as f:
            bench = json.load(f)

    results = run_evaluation(
        args.url,
        bench,
        top_k=args.k,
        api_key=args.api_key,
        faithfulness=not args.no_faithfulness,
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
