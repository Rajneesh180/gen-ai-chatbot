"""LLM generation via Groq — streaming and non-streaming.

Uses Groq's ultra-fast LPU inference with Llama 3.3 70B.
Free tier: 30 RPM, 14,400 RPD — much more generous than Gemini.
"""

from __future__ import annotations

import time
import logging
from typing import Generator, Optional

from backend.config import (
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    get_groq_api_key,
)

logger = logging.getLogger(__name__)

_client = None


def _ensure_client():
    """Initialize the Groq client on first call."""
    global _client
    if _client is not None:
        return

    from groq import Groq

    _client = Groq(api_key=get_groq_api_key())


def generate(prompt: str) -> str:
    """Generate a complete response (non-streaming). For eval/batch use."""
    _ensure_client()
    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_OUTPUT_TOKENS,
    )
    return response.choices[0].message.content


def generate_stream(prompt: str, max_retries: int = 3) -> Generator[str, None, None]:
    """Generate a response with streaming. Yields text chunks as they arrive.

    Includes retry logic with exponential backoff for transient API errors.
    """
    _ensure_client()

    last_error = None
    for attempt in range(max_retries):
        try:
            stream = _client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_OUTPUT_TOKENS,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
            return  # Success
        except Exception as e:
            last_error = e
            error_str = str(e)
            is_retryable = any(code in error_str for code in ["429", "503", "500", "rate_limit"])

            if is_retryable and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                logger.warning(
                    f"[GENERATOR] Groq API error (attempt {attempt + 1}/{max_retries}): "
                    f"{error_str[:120]}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"[GENERATOR] Groq API error (final): {error_str[:200]}")
                raise
