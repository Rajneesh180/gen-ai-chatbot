import os
import sys
import json
import re
from typing import Optional
from pathlib import Path
from collections import deque
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.rag.generator import generate_stream
from backend.rag.prompt import build_prompt, extract_sources
from backend.retrieval.hybrid import retrieve

app = FastAPI(title="GitLab Knowledge API")

# Dynamic CORS: allow configured frontend origin, or all in dev
_ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_FEEDBACK_PATH = _DATA_DIR / "feedback.jsonl"

# ---------------------------------------------------------------------------
# Rate Limiter — protects the free-tier quota
# ---------------------------------------------------------------------------
class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, max_per_minute: int = 10, max_per_day: int = 1400):
        self.max_per_minute = max_per_minute
        self.max_per_day = max_per_day
        self._minute_window: deque = deque()
        self._day_window: deque = deque()

    def _cleanup(self):
        now = time.time()
        while self._minute_window and now - self._minute_window[0] > 60:
            self._minute_window.popleft()
        while self._day_window and now - self._day_window[0] > 86400:
            self._day_window.popleft()

    def check(self) -> Optional[str]:
        """Returns None if allowed, or an error message if rate-limited."""
        self._cleanup()
        if len(self._minute_window) >= self.max_per_minute:
            wait = int(61 - (time.time() - self._minute_window[0]))
            return f"Rate limit: Too many requests. Please wait ~{wait}s before trying again (max {self.max_per_minute} requests/min)."
        if len(self._day_window) >= self.max_per_day:
            return f"Daily limit reached: You've used all {self.max_per_day} daily requests. The quota resets at midnight Pacific Time."
        return None

    def record(self):
        now = time.time()
        self._minute_window.append(now)
        self._day_window.append(now)

    @property
    def usage(self) -> dict:
        self._cleanup()
        return {
            "requests_this_minute": len(self._minute_window),
            "requests_today": len(self._day_window),
            "limit_per_minute": self.max_per_minute,
            "limit_per_day": self.max_per_day,
        }


_rate_limiter = RateLimiter()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    return response


class ChatRequest(BaseModel):
    query: str
    history: list = []


class FeedbackRequest(BaseModel):
    query: str
    answer: str
    rating: str  # "up" or "down"
    comment: str = ""


# ---------------------------------------------------------------------------
# Response parser — extracts metadata & suggestions from LLM output
# ---------------------------------------------------------------------------
def _parse_llm_response(full_text: str) -> dict:
    """Parse the structured LLM response into metadata, answer, and suggestions.

    Expected format:
        <<<META>>>
        {"confidence": 85, "answer_type": "factual", "guardrail_note": ""}
        <<<END_META>>>
        <answer text>
        <<<SUGGESTIONS>>>
        ["q1", "q2", "q3"]
        <<<END_SUGGESTIONS>>>
    """
    result = {
        "metadata": {"confidence": -1, "answer_type": "unknown", "guardrail_note": ""},
        "answer": full_text,
        "suggestions": [],
    }

    # Extract metadata block
    meta_match = re.search(
        r"<<<META>>>\s*(.*?)\s*<<<END_META>>>", full_text, re.DOTALL
    )
    if meta_match:
        try:
            meta = json.loads(meta_match.group(1).strip())
            result["metadata"] = {
                "confidence": meta.get("confidence", -1),
                "answer_type": meta.get("answer_type", "unknown"),
                "guardrail_note": meta.get("guardrail_note", ""),
            }
        except json.JSONDecodeError:
            logger.warning("[PARSER] Failed to parse metadata JSON")

    # Extract suggestions block
    sug_match = re.search(
        r"<<<SUGGESTIONS>>>\s*(.*?)\s*<<<END_SUGGESTIONS>>>", full_text, re.DOTALL
    )
    if sug_match:
        try:
            result["suggestions"] = json.loads(sug_match.group(1).strip())
        except json.JSONDecodeError:
            logger.warning("[PARSER] Failed to parse suggestions JSON")

    # Extract clean answer (everything between the blocks)
    answer = full_text
    # Remove meta block
    answer = re.sub(r"<<<META>>>.*?<<<END_META>>>", "", answer, flags=re.DOTALL)
    # Remove suggestions block
    answer = re.sub(r"<<<SUGGESTIONS>>>.*?<<<END_SUGGESTIONS>>>", "", answer, flags=re.DOTALL)
    result["answer"] = answer.strip()

    return result


# ---------------------------------------------------------------------------
# Retrieval transparency — enrich source data with chunk-level details
# ---------------------------------------------------------------------------
def _build_retrieval_details(chunks: list) -> list:
    """Build detailed retrieval info for the transparency panel."""
    details = []
    for i, chunk in enumerate(chunks):
        details.append({
            "rank": i + 1,
            "title": chunk.get("page_title", "Untitled"),
            "heading": chunk.get("heading_path", ""),
            "url": chunk.get("source_url", ""),
            "rrf_score": round(chunk.get("rrf_score", 0.0), 4),
            "snippet": (chunk.get("text", "")[:150] + "...") if len(chunk.get("text", "")) > 150 else chunk.get("text", ""),
        })
    return details


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/usage")
def usage_stats():
    """Show current API usage against rate limits."""
    return _rate_limiter.usage


@app.post("/api/feedback")
async def feedback_endpoint(req: FeedbackRequest):
    """Log user feedback on a response (thumbs up/down)."""
    try:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "query": req.query,
            "answer_preview": req.answer[:200] if req.answer else "",
            "rating": req.rating,
            "comment": req.comment,
        }
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(_FEEDBACK_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"[FEEDBACK] {req.rating} — query: {req.query[:60]}")
        return {"status": "recorded"}
    except Exception as e:
        logger.error(f"[FEEDBACK] Error saving feedback: {e}")
        return JSONResponse(status_code=500, content={"detail": "Failed to save feedback"})


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        # --- rate-limit guard ---
        rate_msg = _rate_limiter.check()
        if rate_msg:
            logger.warning(f"Rate limited: {_rate_limiter.usage}")
            def rate_limit_stream():
                yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
                yield f"data: {json.dumps({'type': 'retrieval_details', 'details': []})}\n\n"
                yield f"data: {json.dumps({'type': 'metadata', 'metadata': {'confidence': -1, 'answer_type': 'rate_limited', 'guardrail_note': ''}})}\n\n"
                yield f"data: {json.dumps({'type': 'content', 'text': rate_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': []})}\n\n"
                yield 'data: {"type": "done"}\n\n'
            return StreamingResponse(rate_limit_stream(), media_type="text/event-stream")

        # --- retrieval ---
        chunks = retrieve(req.query)
        sources = extract_sources(chunks)
        retrieval_details = _build_retrieval_details(chunks)
        prompt = build_prompt(
            query=req.query,
            chunks=chunks,
            history=req.history,
        )

        def stream_generator():
            # Send sources immediately
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            # Send retrieval transparency details
            yield f"data: {json.dumps({'type': 'retrieval_details', 'details': retrieval_details})}\n\n"

            full_text = ""
            # ----------------------------------------------------------
            # Phase 1: Buffer the ENTIRE LLM response.
            # We do NOT stream raw tokens because the LLM output contains
            # structured metadata (<<<META>>>) and suggestion blocks
            # (<<<SUGGESTIONS>>>) that must be stripped before the user
            # sees them. Buffering first, then parsing, guarantees no
            # metadata ever leaks into the chat UI.
            # ----------------------------------------------------------
            try:
                _rate_limiter.record()
                for chunk_text in generate_stream(prompt):
                    full_text += chunk_text

            except Exception as gen_err:
                logger.error(f"LLM generation error: {gen_err}")
                error_msg = str(gen_err)
                if "429" in error_msg or "ResourceExhausted" in error_msg or "quota" in error_msg.lower():
                    user_msg = "API Rate Limit Reached -- The LLM API free-tier quota has been exhausted. Please wait a few minutes and try again."
                else:
                    user_msg = f"Generation Error: {error_msg[:200]}"
                yield f"data: {json.dumps({'type': 'content', 'text': user_msg})}\n\n"
                yield 'data: {"type": "done"}\n\n'
                return

            # ----------------------------------------------------------
            # Phase 2: Parse the buffered response to separate the clean
            # answer from the metadata and suggestions blocks.
            # ----------------------------------------------------------
            parsed = _parse_llm_response(full_text)

            # Send metadata first (confidence, answer type, guardrails)
            yield f"data: {json.dumps({'type': 'metadata', 'metadata': parsed['metadata']})}\n\n"

            # Send the clean answer (all <<<META>>> / <<<SUGGESTIONS>>> stripped)
            yield f"data: {json.dumps({'type': 'content', 'text': parsed['answer']})}\n\n"

            # Send suggested follow-up questions
            yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': parsed['suggestions']})}\n\n"

            yield 'data: {"type": "done"}\n\n'

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": f"Server Error: {str(e)}"})


# ---------------------------------------------------------------------------
# Serve frontend static files in production (Docker / HuggingFace Spaces)
# The React build output lives at frontend/dist after `npm run build`.
# ---------------------------------------------------------------------------
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIR.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="static-assets")

    # SPA fallback: any non-API route serves index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If a specific static file exists, serve it
        file_path = _FRONTEND_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html (SPA routing)
        return FileResponse(str(_FRONTEND_DIR / "index.html"))

    logger.info(f"[FRONTEND] Serving static files from {_FRONTEND_DIR}")
else:
    logger.info("[FRONTEND] No frontend/dist found — API-only mode")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=(port == 8000))
