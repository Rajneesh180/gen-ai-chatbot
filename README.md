---
title: GitLab Knowledge AI
emoji: 🦊
colorFrom: orange
colorTo: red
sdk: docker
pinned: false
---

# GitLab Knowledge AI

RAG chatbot for answering questions about GitLab's handbook, values, engineering practices, and product direction.

Uses hybrid retrieval (FAISS + BM25 with Reciprocal Rank Fusion), confidence scoring, and real-time streaming via a React chat UI.

**[Live Demo](https://huggingface.co/spaces/rajneeshrehsaan/gitlab-knowledge-ai)**

## Setup

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
export GROQ_API_KEY=your_key_here

# run ingestion
python -m backend.ingestion.run_ingest --all

# backend
uvicorn backend.main:app --reload

# frontend (separate terminal)
cd frontend && npm run dev
```

## Docker

```bash
docker build -t gitlab-knowledge-ai .
docker run -p 7860:7860 -e GROQ_API_KEY=your_key_here gitlab-knowledge-ai
```
