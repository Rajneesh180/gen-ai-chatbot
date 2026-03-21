---
title: Gitlab Knowledge Ai
emoji: 🏢
colorFrom: green
colorTo: red
sdk: docker
pinned: false
---

# GitLab Knowledge AI

RAG chatbot that answers questions about GitLab's internal processes using their public Handbook and Direction pages. Ingests markdown docs, chunks and embeds them, then uses hybrid retrieval (FAISS + BM25) to ground answers in actual content.

**Live demo**: [https://huggingface.co/spaces/rajneeshrehsaan/gitlab-knowledge-ai](https://huggingface.co/spaces/rajneeshrehsaan/gitlab-knowledge-ai)

## How it works

1. Clone GitLab's handbook and direction repos
2. Walk markdown files, clean and split into heading-aware chunks
3. Embed with sentence-transformers (`all-MiniLM-L6-v2`) and build FAISS + BM25 indexes
4. At query time, retrieve via hybrid search (semantic + keyword) with reciprocal rank fusion
5. Pass context to Groq-hosted Llama 3.3 70B for streaming generation

## Stack

- **LLM**: Llama 3.3 70B via Groq (streaming)
- **Embeddings**: all-MiniLM-L6-v2 (local, no API needed)
- **Retrieval**: FAISS (semantic) + BM25 (keyword) with RRF fusion
- **Backend**: FastAPI with SSE streaming
- **Frontend**: React + Vite
- **Deployment**: Docker on Hugging Face Spaces

## Project structure

```
├── backend/
│   ├── config.py               # central configuration
│   ├── main.py                 # FastAPI app + endpoints
│   ├── ingestion/              # data pipeline (clone → walk → chunk → embed → index)
│   ├── retrieval/
│   │   └── hybrid.py           # FAISS + BM25 + RRF fusion
│   ├── rag/
│   │   ├── prompt.py           # system prompt + context assembly
│   │   └── generator.py        # Groq streaming generation
│   └── evaluation/
│       ├── benchmark.py        # offline eval harness
│       └── questions.yaml      # benchmark questions
├── frontend/                   # React chat UI
├── data/                       # index files (faiss.index, bm25.pkl, metadata.pkl)
├── Dockerfile                  # multi-stage build for HF Spaces
└── requirements.txt
```

## Local setup

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..

# set your Groq API key
export GROQ_API_KEY=your_key_here

# run ingestion (if building indexes from scratch)
python -m backend.ingestion.run_ingest --all

# start backend
uvicorn backend.main:app --reload

# start frontend (separate terminal)
cd frontend && npm run dev
```

## Docker

```bash
docker build -t gitlab-knowledge-ai .
docker run -p 7860:7860 -e GROQ_API_KEY=your_key_here gitlab-knowledge-ai
```
