"""RAG prompt assembly — builds the final prompt sent to Gemini.

Responsibilities:
- System prompt with behavior instructions
- Context injection from retrieved chunks with source attribution
- Conversation history formatting
- Query injection
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

SYSTEM_PROMPT = """You are a knowledgeable assistant that answers questions about GitLab's internal processes, \
values, engineering practices, and strategic direction based on their public Handbook and Direction pages.

RULES:
1. Answer ONLY based on the provided context below. Do not use outside knowledge.
2. If the context does not contain enough information to answer the question, say: \
"I don't have enough information from the GitLab handbook to answer that. \
You can try rephrasing your question or check the handbook directly."
3. Cite your sources by referencing the page title and section when you use information from a specific chunk.
4. Keep answers clear, concise, and well-structured. Use bullet points or numbered lists when appropriate.
5. If the question is clearly unrelated to GitLab (e.g., cooking recipes, sports scores), politely redirect: \
"I'm designed to answer questions about GitLab's handbook and direction. How can I help with that?"
6. For follow-up questions, use the conversation history to maintain context.
7. When multiple chunks provide related information, synthesize them into a coherent answer rather than repeating each chunk separately.
"""


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks as numbered context blocks."""
    if not chunks:
        return "No relevant context found."

    parts: List[str] = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source_url", "Unknown source")
        title = chunk.get("page_title", "")
        heading = chunk.get("heading_path", "")
        text = chunk.get("text", "")

        header = f"[Source {i}]"
        if title:
            header += f" {title}"
        if heading:
            header += f" > {heading}"
        header += f"\nURL: {source}"

        parts.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(parts)


def format_history(history: List[Tuple[str, str]], max_turns: int = 4) -> str:
    """Format recent conversation turns for context continuity.

    Each turn is a (user_message, assistant_response) tuple.
    Only includes the last `max_turns` exchanges to keep prompt concise.
    """
    if not history:
        return ""

    recent = history[-max_turns:]
    parts: List[str] = []
    for user_msg, assistant_msg in recent:
        parts.append(f"User: {user_msg}")
        parts.append(f"Assistant: {assistant_msg}")

    return "\n".join(parts)


def build_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    history: List[Tuple[str, str]] | None = None,
) -> str:
    """Assemble the full prompt for the LLM.

    Structure:
    1. System instructions
    2. Retrieved context
    3. Conversation history (if any)
    4. Current user question
    """
    context = format_context(chunks)
    history_text = format_history(history or [])

    parts = [
        SYSTEM_PROMPT.strip(),
        "\n--- CONTEXT ---\n",
        context,
    ]

    if history_text:
        parts.append("\n--- CONVERSATION HISTORY ---\n")
        parts.append(history_text)

    parts.append("\n--- CURRENT QUESTION ---\n")
    parts.append(query)

    return "\n".join(parts)


def extract_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Extract source URLs and titles for citation display in the UI."""
    seen = set()
    sources: List[Dict[str, str]] = []
    for chunk in chunks:
        url = chunk.get("source_url", "")
        title = chunk.get("page_title", "")
        if url and url not in seen:
            seen.add(url)
            sources.append({"url": url, "title": title})
    return sources
