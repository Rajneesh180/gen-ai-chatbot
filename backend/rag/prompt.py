"""RAG prompt assembly — builds the final prompt sent to the LLM.

Responsibilities:
- System prompt with behavior instructions + guardrailing
- Context injection from retrieved chunks with source attribution (page names)
- Conversation history formatting
- Confidence metadata & suggested follow-ups
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

SYSTEM_PROMPT = """\
You are a knowledgeable and friendly assistant that helps users understand GitLab's internal processes, \
values, engineering practices, and strategic direction. Your knowledge comes from GitLab's public \
Handbook and Direction pages.

Think of yourself as a helpful colleague who has read the entire GitLab handbook — answer naturally, \
clearly, and conversationally. Do NOT sound robotic or mechanical.

RULES:
1. Answer ONLY based on the provided context. Do not make things up.
2. If the context doesn't cover the question well enough, honestly say so: \
"I couldn't find detailed information about that in the handbook. \
Try rephrasing, or check the handbook directly."
3. Write your answer in NATURAL LANGUAGE first. Explain concepts clearly with substance. \
Then add 2-3 reference links at the end of relevant sentences or paragraphs using markdown format: \
[Page Title](full URL). These links should feel like a "read more" reference, NOT the main content.
4. NEVER make a link the entire content of a bullet point. Bad: "* [Collaboration](url)". \
Good: "* **Collaboration** — GitLab emphasizes working together across teams, assuming positive intent \
and sharing knowledge openly. See [Values](url) for details."
5. Keep answers well-structured: use bullet points for lists, short paragraphs for explanations. \
Each point should have real substance — a sentence or two explaining what it means, not just a label.
6. If the question is unrelated to GitLab, politely redirect: \
"I'm designed to help with GitLab's handbook and direction. What can I help you with?"
7. For follow-ups, use conversation history for continuity.
8. Synthesize information from multiple sources into one coherent answer. Don't repeat yourself.
9. Keep the tone professional but warm. No excessive emojis.
10. NEVER use bare/raw URLs. NEVER use generic labels like "Source 1" or "Source 2".

RESPONSE FORMAT:
You must structure every response exactly as follows. Do not deviate.

<<<META>>>
{"confidence": <0-100>, "answer_type": "<factual|inferential|insufficient>", "guardrail_note": "<optional caveat or empty string>"}
<<<END_META>>>

<your answer here — natural, conversational, informative>

<<<SUGGESTIONS>>>
["<follow-up question 1>", "<follow-up question 2>", "<follow-up question 3>"]
<<<END_SUGGESTIONS>>>

Metadata field definitions:
- confidence: 0-100 score reflecting how well the provided context supports your answer. \
  90-100 = context directly and fully answers the question. \
  60-89 = context partially covers it, some inference needed. \
  Below 60 = context is weak or tangential.
- answer_type: "factual" if directly from context, "inferential" if you connected pieces, \
  "insufficient" if the context doesn't adequately cover the question.
- guardrail_note: Brief caveat if applicable (e.g. "Only one source mentions this"). \
  Leave as empty string if no caveats.

For the SUGGESTIONS block:
- Generate 3 natural follow-up questions the user might want to ask next.
- Make them specific to the topic just discussed, not generic.
"""


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks as named context blocks using page titles."""
    if not chunks:
        return "No relevant context found."

    parts: List[str] = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source_url", "Unknown source")
        title = chunk.get("page_title", "Untitled Page")
        heading = chunk.get("heading_path", "")
        text = chunk.get("text", "")

        # Use the actual page title as the label, not "Source N"
        header = f"[{title}]"
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
    1. System instructions (with guardrailing + suggestion format)
    2. Retrieved context (with real page titles)
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
