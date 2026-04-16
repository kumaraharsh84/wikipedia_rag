# Scaling Guide

This document outlines how to scale the Wikipedia QA system from a single t2.micro instance to a production-grade architecture handling thousands of concurrent users.

---

## Current Architecture (t2.micro · Free Tier)

```
User → React (port 3000) → FastAPI (port 8000)
                              ├── FAISS index (in-process, RAM)
                              ├── bi-encoder (sentence-transformers)
                              ├── cross-encoder (ms-marco)
                              └── flan-t5-small (CPU inference)
```

**Constraints:** 1 vCPU · 1 GB RAM · CPU-only · single process · ~60s cold start

---

## Scaling Path

### Stage 1 — Vertical Scaling (t2.micro → t3.medium or t3.large)

Cost: ~$30–60/month

- Upgrade to t3.medium (2 vCPU, 4 GB RAM): removes the 2 GB swap requirement
- Set `--workers 2` in uvicorn; FAISS is not thread-safe for writes but read-only queries are fine
- Upgrade to `flan-t5-base` or `flan-t5-large` for better answer quality

No code changes required — just update the instance type and remove `mem_limit` from docker-compose.

---

### Stage 2 — Managed Vector Store (Replace FAISS)

When the FAISS index exceeds ~500k vectors or multi-node support is needed:

**Option A: Pinecone (serverless)**

```python
# pip install pinecone-client
import pinecone

pc = pinecone.Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("wiki-qa")

# Upsert
index.upsert(vectors=[{"id": passage_id, "values": embedding.tolist(), "metadata": {"text": passage, "title": title}}])

# Query
results = index.query(vector=query_embedding.tolist(), top_k=20, include_metadata=True)
passages = [r.metadata["text"] for r in results.matches]
scores   = [r.score            for r in results.matches]
```

**Option B: Weaviate (self-hosted or cloud)**
- Better for hybrid search (BM25 + vector)
- Docker-deployable: `docker run -p 8080:8080 semitechnologies/weaviate`

**Option C: pgvector (PostgreSQL extension)**
- Best if you already use PostgreSQL
- `SELECT * FROM passages ORDER BY embedding <#> $1 LIMIT 20`

---

### Stage 3 — GPU Inference (g4dn.xlarge · $0.526/hr spot)

Replace CPU models with GPU variants:

```python
# In retriever.py / answer_generator.py
device = "cuda" if torch.cuda.is_available() else "cpu"

# Bi-encoder — batched GPU inference
embeddings = model.encode(passages, batch_size=128, device=device, show_progress_bar=False)

# Generator — GPU decoding
model = T5ForConditionalGeneration.from_pretrained("google/flan-t5-large").to(device)
```

In requirements.txt, swap:
```
# CPU
torch==2.3.0
faiss-cpu==1.8.0

# GPU (CUDA 11.8)
torch==2.3.0+cu118 --index-url https://download.pytorch.org/whl/cu118
faiss-gpu==1.8.0
```

Expected latency improvement: 60s → 2–3s first query, sub-500ms cached.

---

### Stage 4 — Async FastAPI + Background Tasks

Convert the `/ask` endpoint to async for concurrent I/O:

```python
from fastapi import BackgroundTasks
from asyncio import get_event_loop
import concurrent.futures

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

@app.post("/ask", response_model=AskResponse)
async def ask(request: Request, req: AskRequest, background_tasks: BackgroundTasks, ...):
    loop = get_event_loop()

    # Run CPU-bound inference in thread pool (non-blocking)
    result = await loop.run_in_executor(_executor, _run_pipeline, req)

    # Save history in background (non-blocking)
    if user:
        background_tasks.add_task(save_history, user["user_id"], req.query, result["answer"])

    return result
```

Add a task queue for heavy operations:

```python
# With Celery + Redis
from celery import Celery
celery_app = Celery("wiki-qa", broker="redis://localhost:6379/0")

@celery_app.task
def index_new_article(title: str):
    """Pre-fetch and index a Wikipedia article in the background."""
    ...
```

---

### Stage 5 — Multi-Service Production Architecture

```
                        ┌─────────────────────┐
                        │   CloudFront (CDN)   │
                        │  React static files  │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   ALB (HTTPS/443)    │
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
    │  FastAPI (ECS)   │ │  FastAPI (ECS)  │ │  FastAPI (ECS)  │
    │  task (2 vCPU)   │ │  task (2 vCPU)  │ │  task (2 vCPU)  │
    └─────────┬────────┘ └────────┬────────┘ └────────┬────────┘
              └────────────────────┼────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
    │   Pinecone       │ │   PostgreSQL     │ │  ElastiCache     │
    │ (vector search)  │ │  (user / auth)   │ │ Redis (cache)    │
    └──────────────────┘ └─────────────────┘ └─────────────────┘
```

**Services to introduce:**
| Component | Current | Production |
|-----------|---------|------------|
| Vector store | FAISS (in-process) | Pinecone / pgvector |
| Cache | TTLCache (in-process) | Redis (ElastiCache) |
| DB | SQLite | PostgreSQL (RDS) |
| Auth | PyJWT (local) | Cognito or Auth0 |
| Compute | t2.micro (1 vCPU) | ECS Fargate / g4dn.xlarge |
| CI/CD | GitHub Actions → Docker Hub | ECR + ECS rolling deploy |
| CDN | None | CloudFront |
| Monitoring | None | CloudWatch + Grafana |

---

## Cost Estimates

| Scenario | Instance | Monthly Cost |
|----------|----------|-------------|
| Development | t2.micro (free tier) | $0 |
| Small production | t3.small + RDS micro | ~$25 |
| Medium production | t3.medium + Pinecone starter | ~$60 |
| GPU inference | g4dn.xlarge (spot) | ~$50–120 |
| High availability | 2× t3.large + ALB + RDS | ~$200 |

---

## Recommended Next Steps

1. **Add Redis caching** — replace TTLCache with `redis-py`; trivially horizontally scalable
2. **Move to Pinecone** — enables semantic search over millions of Wikipedia articles
3. **Switch to flan-t5-large on g4dn.xlarge spot** — best price/performance for answer quality
4. **Add streaming** — FastAPI `StreamingResponse` + `EventSourceResponse` for token-by-token output
5. **Pre-index popular topics** — background Celery task to pre-fetch top 10k Wikipedia articles
