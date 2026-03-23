---
title: GitLab Knowledge AI
emoji: 🦊
colorFrom: orange
colorTo: red
sdk: docker
pinned: false
---

# GitLab Knowledge AI

A production-grade RAG system that answers questions about GitLab's internal processes, values, engineering practices, and product strategy — grounded in their public **Handbook** and **Direction** pages.

The system implements hybrid retrieval (FAISS semantic search + BM25 keyword matching + Reciprocal Rank Fusion), a structured response protocol with confidence scoring, and real-time streaming through a React chat interface.

**[Live Demo](https://huggingface.co/spaces/rajneeshrehsaan/gitlab-knowledge-ai)**

---

## Architecture

```
User Query
   │
   ├─→ Embed (all-MiniLM-L6-v2, 384-d, local)
   │       ├─→ FAISS top-20 (semantic)
   │       └─→ BM25 top-20  (keyword)
   │               │
   │               └─→ RRF Fusion (k=60) → top-5 chunks
   │
   ├─→ Prompt Assembly (system rules + context + history)
   │
   ├─→ Llama 3.3 70B via Groq (streaming SSE)
   │
   └─→ Response Parser → META confidence + answer + follow-up suggestions
```

### Key design decisions

- **Hybrid retrieval, not semantic-only**: BM25 catches GitLab-specific terminology that dense vectors miss. RRF fuses both signals without score calibration.
- **Heading-aware chunking**: Splits on markdown heading boundaries (H2–H5), not fixed character windows. 350–500 token targets with 40-token overlap stitching.
- **Local embeddings**: all-MiniLM-L6-v2 runs on CPU (~50ms/query). No embedding API calls, no data leaving the server.
- **Structured response protocol**: 10-rule system prompt governing citation format, confidence scoring (0–100), scope guards, and follow-up generation.
- **Zero external dependencies at query time**: FAISS and BM25 indexes are loaded into memory at startup. Only the LLM call requires network access.

---

## Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| LLM | Llama 3.3 70B | Groq LPU inference, streaming, temp 0.5, max 2048 tokens |
| Embeddings | all-MiniLM-L6-v2 | 384-d, local CPU, pre-downloaded in Docker build |
| Vector search | FAISS (flat-IP) | Inner-product similarity, exact search |
| Keyword search | BM25 Okapi | rank-bm25, pre-tokenized corpus |
| Fusion | RRF (k=60) | Rank-based aggregation — no score normalization |
| Backend | FastAPI | SSE streaming, CORS, sliding-window rate limiter |
| Frontend | React 19 + Vite | Streaming chat, transparency panel, feedback, export |
| Deployment | Docker multi-stage | Node 20 → Python 3.9, single image, port 7860 |

---

## Project structure

```
├── backend/
│   ├── config.py                   # central configuration & tunables
│   ├── main.py                     # FastAPI app, endpoints, rate limiter, response parser
│   ├── ingestion/
│   │   ├── run_ingest.py           # CLI entry: clone → walk → chunk → embed → index
│   │   ├── md_loader.py            # markdown walker + frontmatter extraction
│   │   ├── chunker.py              # heading-aware chunker (350-500 tokens, overlap stitching)
│   │   ├── embedder.py             # batch embedding with sentence-transformers
│   │   ├── indexer.py              # FAISS + BM25 index builder
│   │   ├── url_mapper.py           # file path → live GitLab URL mapping
│   │   └── schema.py              # Chunk dataclass + token estimation
│   ├── retrieval/
│   │   └── hybrid.py               # FAISS + BM25 + RRF fusion engine
│   ├── rag/
│   │   ├── prompt.py               # system prompt (10 rules) + context assembly
│   │   └── generator.py            # Groq streaming with retry + backoff
│   └── evaluation/
│       ├── benchmark.py            # offline eval harness (retrieve → prompt → generate → score)
│       └── questions.yaml          # benchmark question set
├── frontend/
│   └── src/
│       ├── App.jsx                 # main app: chat UI, topic starters, architecture pills
│       ├── hooks/useChatStream.js  # SSE streaming hook with abort + persistence
│       └── components/             # Auth, Chat, Admin, Layout, UI modules
├── data/                           # runtime artifacts (faiss.index, bm25.pkl, metadata.pkl)
├── Dockerfile                      # multi-stage: Node 20 build → Python 3.9 runtime
└── requirements.txt
```

---

## Local development

```bash
# install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# set Groq API key
export GROQ_API_KEY=your_key_here

# run ingestion pipeline (clones repos, chunks, embeds, indexes)
python -m backend.ingestion.run_ingest --all

# start backend (port 8000)
uvicorn backend.main:app --reload

# start frontend (port 5173, separate terminal)
cd frontend && npm run dev
```

## Docker

```bash
docker build -t gitlab-knowledge-ai .
docker run -p 7860:7860 -e GROQ_API_KEY=your_key_here gitlab-knowledge-ai
```

The Docker image includes pre-computed indexes and a pre-downloaded embedding model — no ingestion needed at runtime.
