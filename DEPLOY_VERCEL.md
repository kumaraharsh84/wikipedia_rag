# Vercel Deployment

This repo is prepared for a single Vercel project:

- the React app is built from `frontend_react/`
- the FastAPI app is exposed through `api/index.py`
- the frontend talks to `/api` by default, which matches the Vercel function path

## Before You Deploy

Set these environment variables in Vercel:

```bash
JWT_SECRET=your-long-random-secret
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.3-70b-versatile
ENABLE_RERANKER=false
ENABLE_GENERATOR=false
VECTOR_STORE=pinecone
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX=wiki-qa
```

## Why Those Settings

- `VECTOR_STORE=pinecone`: local FAISS files are not durable on Vercel
- `ENABLE_RERANKER=false`: reduces cold start and memory pressure
- `ENABLE_GENERATOR=false`: avoids local transformer fallback on serverless instances

If you want reranking later, enable it only after confirming your deployment size and runtime are still acceptable.

## Deploy Steps

1. Push the repo to GitHub.
2. Import the repo into Vercel.
3. Keep the Root Directory as the repository root.
4. Add the environment variables above.
5. Deploy.

## Important Runtime Notes

- Vercel Functions use ephemeral storage. This repo now writes temp runtime data to `/tmp` on Vercel so it can run, but that data is not persistent.
- SQLite auth/history on Vercel should be treated as demo-only. For real persistence, move auth/history to an external database.
- Pinecone is strongly recommended for production Vercel deployments.
- Very long requests can still hit Vercel function duration limits, especially if you re-enable heavy local models.
