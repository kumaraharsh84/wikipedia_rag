# ─────────────────────────────────────────────────────────────────────────────
# Wikipedia Smart QA — Dockerfile v2
#
# All three models and NLTK data are baked into the image at build time so
# the EC2 instance never downloads anything at runtime. Slow once to build,
# fast forever after.
#
# Image layers (in cache-friendly order):
#   1. System packages
#   2. Python dependencies
#   3. NLTK punkt data
#   4. Sentence-transformer (bi-encoder)
#   5. Cross-encoder
#   6. flan-t5-small (generator)
#   7. Application source (changes most often — last so above layers stay cached)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Layer 2: Python dependencies ──────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Layer 3: NLTK punkt tokenizer data ───────────────────────────────────────
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"

# ── Layer 4: Bi-encoder (sentence-transformer) ────────────────────────────────
RUN python -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
print('Bi-encoder cached.')
"

# ── Layer 5: Cross-encoder (re-ranker) ───────────────────────────────────────
RUN python -c "
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
print('Cross-encoder cached.')
"

# ── Layer 6: flan-t5-small (answer generator) ────────────────────────────────
RUN python -c "
from transformers import T5ForConditionalGeneration, T5Tokenizer
T5Tokenizer.from_pretrained('google/flan-t5-small')
T5ForConditionalGeneration.from_pretrained('google/flan-t5-small')
print('flan-t5-small cached.')
"

# ── Layer 7: Application source ───────────────────────────────────────────────
COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
