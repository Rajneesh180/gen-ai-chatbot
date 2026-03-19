"""Central configuration for the GitLab Knowledge Chatbot."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPOS_DIR = DATA_DIR / "repos"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
FAISS_PATH = DATA_DIR / "faiss.index"
BM25_PATH = DATA_DIR / "bm25.pkl"
METADATA_PATH = DATA_DIR / "metadata.pkl"

# ---------------------------------------------------------------------------
# Embedding model config (local — no API needed)
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMS = 384
EMBEDDING_BATCH_SIZE = 128

# ---------------------------------------------------------------------------
# LLM config — Groq (free tier: 30 RPM, 14,400 RPD)
# ---------------------------------------------------------------------------
LLM_PROVIDER = "groq"
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.5
LLM_MAX_OUTPUT_TOKENS = 2048

# ---------------------------------------------------------------------------
# Chunking tunables
# ---------------------------------------------------------------------------
CHUNK_TARGET_MIN = 350
CHUNK_TARGET_MAX = 500
CHUNK_HARD_CAP = 700

# ---------------------------------------------------------------------------
# Retrieval tunables
# ---------------------------------------------------------------------------
RETRIEVAL_K = 5
FAISS_SEARCH_K = 20
BM25_SEARCH_K = 20
RRF_K = 60

# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------
def get_groq_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    break
    if not key:
        raise SystemExit(
            "GROQ_API_KEY not set. Add it to .env or export it."
        )
    return key


# Keep backward compat alias
def get_api_key() -> str:
    return get_groq_api_key()
