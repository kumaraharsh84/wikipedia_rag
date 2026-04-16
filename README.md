# WikiQA — RAG-based Question Answering over Wikipedia

A full-stack Retrieval-Augmented Generation system that answers natural-language questions using live Wikipedia data. It was built to understand the engineering trade-offs in a real RAG pipeline — not just to call an LLM API.

The core design decisions worth discussing in an interview:

- **Why two retrieval stages?** The bi-encoder (FAISS) is fast but scores query and passage independently. The cross-encoder re-ranks the candidate set jointly, raising Precision@k from ~0.60 to ~0.80 at the cost of ~500ms. Whether that trade-off is worth it depends on use case.
- **Source diversity enforcement** — a custom post-ranking step that guarantees at least one passage per fetched Wikipedia article appears in the final top-k. Without it, the cross-encoder fills all slots from the single most-relevant article and silently drops context from other sources. This isn't covered in RAG tutorials but matters in production when queries span multiple topics.
- **Sentence-boundary chunking with configurable overlap** — passages always start and end at sentence boundaries (NLTK), unlike naive word-count windows that cut mid-sentence. Overlap of 1 sentence between adjacent passages avoids losing context at chunk edges.
- **Content-hash FAISS persistence** — the index is keyed by an MD5 of passage content, so re-running the same query skips both re-encoding and re-fetching.

```
┌─────────────────────────────┐  SSE stream   ┌──────────────────────────────────────────────┐
│  React 18 Frontend          │ ────────────►  │  FastAPI Backend (v4)                        │
│  Vite · Tailwind · :3000    │               │  1. Fetch 1–5 Wikipedia articles              │
│  Streaming chat UI          │ ◄────────────  │  2. Split into passages  (NLTK chunking)      │
│  History · Benchmark · Auth │  token/done   │  3. Encode  — sentence-transformers           │
└─────────────────────────────┘               │  4. Vector search — FAISS  or  Pinecone       │
                                               │  5. Cross-encoder re-ranking                  │
                                               │  6. LLM answer  — Groq / OpenAI / Anthropic  │
                                               │  7. TTL cache · Prometheus metrics            │
                                               └──────────────────────────────────────────────┘
```

---

## Problem Statement

Search engines return links. LLMs hallucinate. **WikiQA bridges the gap:**

- **Who uses this:** Students, researchers, and developers who need fast, cited answers grounded in real knowledge — not fabricated responses.
- **Real-world analogy:** Think Perplexity AI, but open-source, self-hostable, and fully auditable.
- **Why it matters:** RAG (Retrieval-Augmented Generation) is the dominant pattern for production AI systems at companies like Google, Meta, and OpenAI. This project implements that pattern end-to-end.

---

## Features

| Category | What's included |
|----------|----------------|
| **RAG pipeline** | Bi-encoder retrieval → cross-encoder re-ranking → LLM generation |
| **Multi-article** | Fetches 1–5 Wikipedia articles, merges passages with per-source tracking |
| **Token streaming** | `/ask/stream` SSE endpoint — status events + word-by-word tokens like ChatGPT |
| **Multi-LLM** | `groq` (llama-3.3-70b, **free**) · `openai` · `anthropic` · `local` (flan-t5-small, no key) |
| **Conversation memory** | Full multi-turn context — prior Q&A injected into each LLM request |
| **Abort streaming** | Stop button cancels in-flight SSE stream instantly (AbortController) |
| **LaTeX rendering** | Inline `$...$` and block `$$...$$` math rendered via KaTeX |
| **Vector store** | `VECTOR_STORE=faiss` (default, local) · `pinecone` (serverless, cloud) |
| **React chat UI** | Premium dark "Emerald Nocturne" design — streaming bubbles, confidence-scored passage cards, related topic chips |
| **History analytics** | Bento-grid research history with topic distribution charts and sort/filter |
| **Explainability** | Every retrieved passage shows a colour-coded confidence bar (High / Medium / Low) |
| **JWT auth** | Register/login, per-user query history in SQLite |
| **Benchmark page** | In-app Precision@k, MRR, faithfulness (LLM-as-judge), and latency across 5 queries |
| **Observability** | `/metrics/prometheus` + Prometheus + Grafana dashboard (docker-compose) |
| **Production** | Rate limiting, API key auth, Docker, GitHub Actions CI/CD, EC2 free-tier optimised |

---

## How It Works

| Step | Component | What happens |
|------|-----------|--------------|
| 1 | `wikipedia_api.py` | Searches Wikipedia, fetches 1–5 articles, handles disambiguation |
| 2 | `text_cleaner.py` | Strips markup/citations, splits into overlapping sentence chunks (NLTK) |
| 3 | `embeddings.py` | Encodes passages with `all-MiniLM-L6-v2` → 384-dim L2-normalised vectors |
| 4 | `search.py` | FAISS `IndexFlatIP` (cosine) **or** Pinecone serverless query |
| 5 | `reranker.py` | Cross-encoder (`ms-marco-MiniLM-L-6-v2`) re-scores top passages; `enforce_source_diversity()` guarantees ≥1 passage per fetched article |
| 6 | `answer_generator.py` | Chosen LLM synthesises answer with conversation history; `stream_tokens()` yields word-by-word |
| 7 | `cache.py` | 1-hour TTL cache; FAISS index persisted to disk; Prometheus metrics |

---

## Tech Stack Comparison

### FAISS vs Pinecone

| | FAISS (default) | Pinecone |
|-|----------------|----------|
| **Setup** | Zero config, local | Requires account + API key |
| **Latency** | ~5–20 ms | ~50–100 ms (network) |
| **Scale** | Single node, fits in RAM | Serverless, unlimited scale |
| **Cost** | Free | Free tier, then pay-per-query |
| **Best for** | Dev, t2.micro, offline | Production, multi-user, cloud |
| **Persistence** | File on disk (`data/faiss.index`) | Managed cloud index |

Switch with: `VECTOR_STORE=faiss` or `VECTOR_STORE=pinecone`

---

### With vs Without Cross-Encoder Reranker

| | Without reranker | With reranker |
|-|-----------------|---------------|
| **Method** | Bi-encoder cosine similarity only | Bi-encoder + cross-encoder re-scoring |
| **Precision@k** | ~0.55–0.65 | ~0.75–0.85 |
| **Latency** | ~300 ms | ~800 ms (+500 ms) |
| **RAM** | ~200 MB | ~350 MB |
| **Best for** | t2.micro RAM-constrained, fast demos | Accuracy-critical queries |

Switch with: `ENABLE_RERANKER=true` (default) or `ENABLE_RERANKER=false`

---

### LLM Provider Comparison

| Provider | Model | Quality | Cost | Latency |
|----------|-------|---------|------|---------|
| **Groq** (default) | llama-3.3-70b-versatile | ⭐⭐⭐⭐⭐ | Free | ~0.5–1s |
| OpenAI | gpt-4o-mini | ⭐⭐⭐⭐⭐ | ~$0.001/query | ~1–2s |
| Anthropic | claude-haiku-4-5 | ⭐⭐⭐⭐⭐ | ~$0.001/query | ~1–2s |
| Local | flan-t5-small | ⭐⭐ | Free, no internet | ~2–5s |

---

## Project Structure

```
wiki/
├── backend/
│   ├── main.py             # FastAPI — /ask, /ask/stream, /auth/*, /metrics, /evaluate
│   ├── auth.py             # JWT create/decode, bcrypt password hashing
│   ├── database.py         # SQLite — users + query history
│   ├── answer_generator.py # Multi-LLM: Groq / OpenAI / Anthropic / flan-t5 + conversation memory
│   ├── search.py           # FAISS IndexFlatIP + Pinecone drop-in (VECTOR_STORE flag)
│   ├── reranker.py         # Cross-encoder re-ranking + enforce_source_diversity()
│   ├── embeddings.py       # Sentence-transformer singleton (all-MiniLM-L6-v2)
│   ├── wikipedia_api.py    # Wikipedia fetch & disambiguation handling
│   └── cache.py            # TTL in-memory response cache
├── frontend_react/         # React 18 + Vite + Tailwind CSS (Emerald Nocturne design)
│   └── src/
│       ├── App.jsx               # Root — streaming chat loop, JWT state, view routing, abort
│       ├── api.js                # askStream() async generator + ask/login/register/history
│       └── components/
│           ├── AuthModal.jsx     # Login / register modal
│           ├── ChatMessage.jsx   # User / streaming / assistant / error bubbles + LaTeX
│           ├── QueryInput.jsx    # Glass input bar — send button + red abort button
│           ├── Sidebar.jsx       # Nav sidebar + SettingsPanel export
│           ├── PassageCard.jsx   # Passage card with colour-coded confidence bar + source link
│           ├── HistoryView.jsx   # Bento-grid history with analytics stats + sort/filter
│           └── EvalView.jsx      # Benchmark page — Precision@k, MRR, faithfulness, latency
├── eval/
│   └── evaluate.py         # CLI benchmark — Precision@k, MRR, faithfulness (LLM-as-judge), latency
├── tests/
│   ├── test_api.py         # Integration tests — API shape, auth, caching
│   └── test_pipeline.py    # Unit tests — chunking, cache, reranker, source diversity
├── utils/
│   ├── text_cleaner.py     # NLTK sentence chunking, Wikipedia markup strip
│   └── logger.py           # Centralized logging
├── scripts/
│   ├── push_to_dockerhub.sh  # Build locally and push to Docker Hub
│   └── ec2_setup.sh          # EC2 one-shot setup (swap + Docker + deploy)
├── grafana/provisioning/   # Auto-provisioned Prometheus datasource + dashboard
├── prometheus.yml          # Prometheus scrape config
├── data/                   # FAISS index + SQLite DB (auto-created, gitignored)
├── SCALING.md              # Scaling guide: Pinecone, GPU, async, AWS architecture
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── pytest.ini
```

---

## Quick Start (Local)

### Prerequisites

- Python 3.10 or 3.11
- Node.js 18+
- Free Groq API key → [console.groq.com](https://console.groq.com)

### 1 — Configure environment

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY=gsk_...
```

> **Important:** The backend reads all settings from `.env` via `python-dotenv`. Without setting `GROQ_API_KEY`, it silently falls back to the local flan-t5-small model (short, low-quality answers).

### 2 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3 — Start the FastAPI backend

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 4 — Start the React frontend

```bash
cd frontend_react
npm install
npm run dev
# → http://localhost:3000
```

### 5 — API docs

FastAPI interactive docs at **http://localhost:8000/docs**

---

## Docker (Recommended)

```bash
# Start all services: backend + React + Prometheus + Grafana
docker compose up --build

# Backend     → http://localhost:8000
# React       → http://localhost:3000
# Prometheus  → http://localhost:9090
# Grafana     → http://localhost:3001  (admin / admin)
```

---

## Switching LLM Provider

```bash
# Default — Groq Cloud (FREE, fast, llama-3.3-70b-versatile)
# Get a free API key at https://console.groq.com
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile   # optional override

# OpenAI (gpt-4o-mini by default)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini             # optional override

# Anthropic (Claude Haiku by default)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # optional override

# Local — flan-t5-small, CPU, no API key needed (lower quality)
LLM_PROVIDER=local
```

---

## Switching Vector Store

```bash
# Default — FAISS (local, zero config)
VECTOR_STORE=faiss

# Pinecone serverless (create index in Pinecone console first)
VECTOR_STORE=pinecone
PINECONE_API_KEY=...
PINECONE_INDEX=wiki-qa
```

---

## Cloud Deployment on AWS EC2 Free Tier

Optimised for **t2.micro** (1 GB RAM). Build the image locally and push to Docker Hub — EC2 only pulls and runs.

### Step 1 — Launch EC2

- AMI: **Ubuntu 22.04 LTS** · Instance type: **t2.micro** · Storage: **16 GB** gp2
- Security Group inbound rules:

| Port | Source | Purpose |
|------|--------|---------|
| 22 | Your IP | SSH |
| 8000 | 0.0.0.0/0 | FastAPI backend |
| 3000 | 0.0.0.0/0 | React frontend |
| 9090 | Your IP | Prometheus |
| 3001 | Your IP | Grafana |

### Step 2 — Build & push from your local machine

```bash
chmod +x scripts/push_to_dockerhub.sh
./scripts/push_to_dockerhub.sh yourdockerhubname
```

### Step 3 — Deploy on EC2

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>
scp -i your-key.pem scripts/ec2_setup.sh docker-compose.yml prometheus.yml ubuntu@<EC2_PUBLIC_IP>:~/
chmod +x ec2_setup.sh
./ec2_setup.sh yourdockerhubname/wiki-qa:latest <EC2_PUBLIC_IP>
```

### Step 4 — Access

| Service | URL |
|---------|-----|
| React UI | `http://<EC2_PUBLIC_IP>:3000` |
| API docs | `http://<EC2_PUBLIC_IP>:8000/docs` |
| Prometheus | `http://<EC2_PUBLIC_IP>:9090` |
| Grafana | `http://<EC2_PUBLIC_IP>:3001` |

---

## API Reference

### `POST /ask` — Full JSON response

```json
// Request
{
  "query": "What is Quantum Computing?",
  "top_k": 5,
  "num_articles": 2,
  "rerank": true,
  "history": [
    {"role": "user",      "content": "What is a qubit?"},
    {"role": "assistant", "content": "A qubit is..."}
  ]
}

// Response
{
  "query": "What is Quantum Computing?",
  "answer": "Quantum computing uses quantum mechanical phenomena...",
  "primary_title": "Quantum computing",
  "primary_url": "https://en.wikipedia.org/wiki/Quantum_computing",
  "passages": [
    {"passage": "...", "score": 0.8921, "source": {"title": "Quantum computing", "url": "..."}}
  ],
  "sources": [{"title": "Quantum computing", "url": "..."}],
  "related_topics": ["Qubit", "Superposition", "Quantum entanglement"],
  "cached": false,
  "latency_ms": 1240
}
```

### `POST /ask/stream` — Server-Sent Events

Emits a sequence of JSON events:

```
data: {"type": "status",  "content": "Searching Wikipedia…"}
data: {"type": "status",  "content": "Generating answer…"}
data: {"type": "token",   "content": "Quantum "}
data: {"type": "token",   "content": "computing "}
data: {"type": "done",    "answer": "...", "passages": [...], "sources": [...], ...}
```

The React frontend uses this endpoint by default for a ChatGPT-like streaming UX.

### `POST /auth/register` · `POST /auth/login`

```json
{ "username": "alice", "password": "secret123" }
→ { "access_token": "<JWT>", "username": "alice" }
```

Pass `Authorization: Bearer <token>` on `/ask` or `/ask/stream` to save query history.

### `GET /auth/history`

Returns the authenticated user's last 20 queries.

### `GET /evaluate`

Built-in benchmark — Precision@k and MRR@k across 5 queries. Also available as the in-app Benchmark page.

### `GET /metrics/prometheus`

Prometheus-format metrics (request counts, latency histograms, error rates).

### `GET /health`

Returns `{"status": "ok", "version": "4.0.0"}`.

---

## Observability

Prometheus scrapes `/metrics/prometheus` every 15 seconds. Grafana auto-connects on startup.

**Key metrics exposed:**
- `http_requests_total` — request count by endpoint and status code
- `http_request_duration_seconds` — latency histogram (p50/p95/p99)
- `http_requests_in_progress` — in-flight request count

Access Grafana at `http://localhost:3001` (default: admin/admin).

---

## Running the Evaluation Suite

```bash
# CLI
python eval/evaluate.py --url http://localhost:8000
python eval/evaluate.py --url http://localhost:8000 --out results.json

# Or use the in-app Benchmark page: click "Benchmark" in the sidebar
```

Outputs Precision@k, MRR@k, faithfulness (LLM-as-judge), and p50/p95/p99 latency across 8 benchmark queries.

Faithfulness scoring uses the same LLM as the generator (Groq by default) to ask: *"Given only these passages, is this answer supported? YES or NO."* This detects hallucination — claims the LLM introduced that aren't in the retrieved Wikipedia text. Requires `GROQ_API_KEY`; omitted silently otherwise.

---

## Running Tests

```bash
pytest
```

46 tests across two suites:
- `tests/test_api.py` — integration tests: API shape, auth flow, cache headers
- `tests/test_pipeline.py` — unit tests: text cleaning, passage chunking, FAISS cache eviction, reranker fallbacks, **source diversity enforcement**

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | LLM backend: `groq` (free), `openai`, `anthropic`, `local` |
| `GROQ_API_KEY` | — | Required when `LLM_PROVIDER=groq` — free at console.groq.com |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model override |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model override |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Anthropic model override |
| `VECTOR_STORE` | `faiss` | Vector backend: `faiss` or `pinecone` |
| `PINECONE_API_KEY` | — | Required when `VECTOR_STORE=pinecone` |
| `PINECONE_INDEX` | `wiki-qa` | Pinecone index name |
| `API_KEY` | _(empty)_ | `X-API-Key` header — leave blank to disable |
| `JWT_SECRET` | `change-me-in-production` | JWT signing secret — **always set in production** |
| `ENABLE_RERANKER` | `true` | Set `false` to skip cross-encoder (saves ~150 MB RAM) |
| `ENABLE_GENERATOR` | `true` | Set `false` to skip local LLM (saves ~500 MB RAM) |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |

---

## RAM Profiles (t2.micro — 1 GB RAM + 2 GB swap required)

| Mode | RAM usage | How to enable |
|------|-----------|---------------|
| Full (reranker + local LLM) | ~950 MB | Default with `LLM_PROVIDER=local` |
| No local generator | ~450 MB | `ENABLE_GENERATOR=false` |
| Bi-encoder only | ~300 MB | `ENABLE_RERANKER=false ENABLE_GENERATOR=false` |
| Groq / OpenAI / Anthropic API | ~300 MB | `LLM_PROVIDER=groq` + `ENABLE_GENERATOR=false` |

---

## Scaling

See [SCALING.md](SCALING.md) for a full guide covering:
- Pinecone / Weaviate / pgvector for managed vector search
- GPU inference on g4dn.xlarge (~10× faster)
- Async FastAPI with `run_in_executor` and Celery task queues
- Multi-service AWS architecture with ECS, ALB, RDS, ElastiCache, and CloudFront
- Cost estimates from $0 (free tier) to $200/month (high availability)

---

## Known Limitations

This is an honest account of what the system handles poorly. These are documented design trade-offs, not overlooked bugs.

| Limitation | Root cause | How I'd address it |
|------------|-----------|-------------------|
| **Multi-hop questions** — "Who is the president of the country that invented the internet?" | Single-pass retrieval; pipeline can't chain lookups | Chain-of-thought retrieval or a query decomposition step before the first FAISS call |
| **Post-2024 knowledge gaps** — recent events may return stale or empty Wikipedia articles | Wikipedia coverage is finite; no indexing of live news | Add a news API fallback (e.g. NewsAPI) for queries with temporal signals ("recent", "2025", "last week") |
| **Disambiguation ambiguity** — "What is Mercury?" retrieves passages about the planet, element, and Roman god simultaneously | Wikipedia disambiguation pages are silently resolved to the first option | Detect when multiple semantically distant articles are fetched and surface a clarifying question to the user before retrieval |
| **NLTK chunking breaks on non-prose content** — code snippets, tables, mathematical notation, and lists break the sentence tokenizer | NLTK `sent_tokenize` assumes natural-language prose | Use a structure-aware splitter (e.g. detect Markdown tables / code fences) and fall back to fixed-length chunking for non-prose sections |
| **No per-user retrieval personalisation** — all users get identical results for identical queries | Implemented as a shared cache; no user embedding profiles | Could weight topic embeddings by prior query history, but this risks filter bubbles and requires explicit user consent design — deferred intentionally |

---

## Interview Talking Points

**"Walk me through your RAG pipeline."**
> "Query → bi-encoder retrieval over a FAISS index → cross-encoder re-ranking → source-diversity enforcement → LLM generation with conversation history → SSE streaming. Each stage has a measurable cost/benefit. The interesting engineering decision is the re-ranker: +20 points of Precision@k at +500ms latency. For a search use-case that's usually worth it; for a real-time chat assistant you might skip it."

**"What's the source diversity step — I haven't seen that in tutorials."**
> "When you fetch 2–5 Wikipedia articles, the cross-encoder can legitimately put all 5 top-k slots from one article and drop the others entirely. That's great for precision but bad for the LLM's context breadth. I added an O(n) post-processing step that reserves one slot per unique source before filling remaining slots by score. It costs nothing in latency and noticeably improves answer quality on multi-topic queries."

**"Why FAISS over pgvector or a managed vector DB?"**
> "FAISS is in-process and does sub-20ms exact cosine search. pgvector makes sense when you need SQL joins or multi-tenancy. Pinecone is the right call at scale — I built it as a drop-in swap behind a `VECTOR_STORE` flag so I can benchmark both. For a single-node demo, FAISS with content-hash-keyed disk persistence is the simplest thing that works."

**"How did you measure retrieval quality?"**
> "Precision@k and MRR. P@k measures what fraction of the top-k passages contain the answer. MRR measures the reciprocal rank of the first relevant passage — it penalises burying the right answer at position 4 out of 5. I ran both on 8 benchmark queries. With reranking: P@5 ≈ 0.80, MRR ≈ 0.85. Without: P@5 ≈ 0.60, MRR ≈ 0.68."

**"How do you know the LLM isn't hallucinating?"**
> "Retrieval metrics like P@k tell you whether the right passages were found — but not whether the LLM stayed faithful to them. I added an LLM-as-judge faithfulness check: after generating an answer, the same model is asked 'Given only these passages, is this answer supported? YES or NO.' It's the same pattern Cohere's RAG evaluator and the Ragas framework use. It's not ground-truth, but it catches the most common failure mode — the LLM generating plausible-sounding facts that aren't in the retrieved text."

---

## License

MIT — free to use, modify, and deploy.
