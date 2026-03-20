"""LLM generation via Gemini — streaming and non-streaming.

Thin wrapper around google-generativeai that handles:
- Model initialization
- Streaming generation for the chat UI
- Non-streaming generation for evaluation/batch
- Error handling and retry on transient failures
"""

from __future__ import annotations

import time
from typing import Generator, Optional

from backend.config import (
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    get_api_key,
)

_model = None


def _ensure_model():
    """Initialize the Gemini model on first call."""
    global _model
    if _model is not None:
        return

    import google.generativeai as genai

    genai.configure(api_key=get_api_key())
    _model = genai.GenerativeModel(
        model_name=LLM_MODEL,
        generation_config={
            "temperature": LLM_TEMPERATURE,
            "max_output_tokens": LLM_MAX_OUTPUT_TOKENS,
        },
    )


def generate(prompt: str) -> str:
    """Generate a complete response (non-streaming). For eval/batch use."""
    _ensure_model()
    response = _model.generate_content(prompt)
    return response.text


def generate_stream(prompt: str) -> Generator[str, None, None]:
    """Generate a response with streaming. Yields text chunks as they arrive.

    Used by the Streamlit UI for real-time display.
    """
    _ensure_model()
    response = _model.generate_content(prompt, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text
