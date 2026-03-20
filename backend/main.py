import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.rag.generator import generate_stream
from backend.rag.prompt import build_prompt, extract_sources
from backend.retrieval.hybrid import retrieve

app = FastAPI(title="GitLab Knowledge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    history: list = []  # List of [user_query, assistant_response]

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        chunks = retrieve(req.query)
        sources = extract_sources(chunks)
        prompt = build_prompt(
            query=req.query,
            chunks=chunks,
            history=req.history,
        )

        def stream_generator():
            # Send sources first as a special event, or just yield the text
            # We can use Server-Sent Events (SSE) format to send metadata and text
            import json
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            
            for chunk_text in generate_stream(prompt):
                yield f"data: {json.dumps({'type': 'content', 'text': chunk_text})}\n\n"

            yield "data: {\"type\": \"done\"}\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
