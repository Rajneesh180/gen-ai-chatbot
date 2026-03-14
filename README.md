# gen-ai-chatbot

A chatbot that answers questions about GitLab's internal processes using their public Handbook and Direction pages.

Built this as part of an internship assignment — the idea is to ingest GitLab's docs, chunk and embed them, and then use retrieval-augmented generation to ground the chatbot's answers in actual content instead of hallucinating.

## how it works

1. Clone GitLab's handbook and direction repos
2. Walk through the markdown files, clean them up, split into chunks
3. Embed chunks and build a FAISS index + BM25 index for hybrid search
4. At query time, retrieve relevant chunks using both semantic and keyword search, fuse the results, and pass them as context to Gemini

## stack

- **LLM**: Gemini 2.0 Flash (free tier)
- **Embeddings**: Google text-embedding-004
- **Retrieval**: FAISS (semantic) + BM25 (keyword) with reciprocal rank fusion
- **UI**: Streamlit

## setup

```bash
pip install -r requirements.txt
```

More details on running the full pipeline coming soon as I build it out.
