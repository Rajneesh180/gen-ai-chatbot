"""
Chunk data model for the ingestion pipeline.

Every document section that passes through the pipeline ends up as a Chunk.
The schema is intentionally flat — one dataclass, no inheritance, no ORM.
Downstream stages (embedder, indexer, retrieval) all consume Chunk dicts
read from data/chunks.jsonl.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, Tuple


# Rough multiplier: avg English word ≈ 1.3 tokens for most embedding models.
# Not exact, but good enough for budget math without pulling in tiktoken.
_WORD_TO_TOKEN_RATIO = 1.3


@dataclass(frozen=True)
class Chunk:
    """Single retrieval unit produced by the chunker.

    Fields are ordered by importance to downstream consumers:
    - text/source_url go into the RAG prompt
    - heading_path/page_title help the LLM cite sources
    - token_count/breadcrumb_tokens enable prompt budget math
    - file_path/chunk_index are debug-only
    """

    chunk_id: str                # sha256(file_path + heading_path + chunk_index)[:12]
    text: str                    # chunk content with heading breadcrumb prepended
    source_url: str              # public GitLab URL for citation
    page_title: str              # from YAML frontmatter "title" field
    heading_path: str            # "Collaboration > Kindness"
    heading_parts: Tuple[str, ...]  # ("Collaboration", "Kindness") — for filtering/UI hierarchy
    heading_level: int           # deepest heading level in this chunk (2, 3, 4...)
    source_type: str             # "handbook" or "direction"
    section: str                 # top-level slug: "values", "engineering", etc.
    token_count: int             # estimated tokens in text
    breadcrumb_tokens: int       # estimated tokens in the breadcrumb prefix alone
    file_path: str               # relative to repo root
    chunk_index: int = 0         # position within the source file (0-based)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict suitable for JSON output."""
        return asdict(self)

    def to_json_line(self) -> str:
        """Single JSON line for chunks.jsonl — no trailing newline.

        Uses compact separators to keep JSONL small and deterministic.
        """
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Chunk:
        """Reconstruct a Chunk from a dict (e.g. read back from JSONL)."""
        d = dict(d)
        # heading_parts stored as list in JSON, convert back to tuple
        if "heading_parts" in d and isinstance(d["heading_parts"], list):
            d["heading_parts"] = tuple(d["heading_parts"])  # type: ignore[arg-type]
        return cls(**d)

    @classmethod
    def from_raw_section(
        cls,
        content: str,
        file_path: str,
        source_url: str,
        page_title: str,
        heading_path: str,
        heading_level: int,
        source_type: str,
        section: str,
        chunk_index: int = 0,
    ) -> Chunk:
        """Build a Chunk from a raw parsed markdown section.

        This is the primary constructor used by the chunker stage.
        It handles breadcrumb prepending, token estimation, and ID generation
        so the chunker doesn't need to know those details.
        """
        breadcrumb = _build_breadcrumb(page_title, heading_path)
        breadcrumb_tok = estimate_tokens(breadcrumb)
        full_text = f"{breadcrumb}\n\n{content}" if breadcrumb else content
        token_count = estimate_tokens(full_text)

        chunk_id = build_chunk_id(file_path, heading_path, chunk_index)
        heading_parts = tuple(h.strip() for h in heading_path.split(">")) if heading_path else ()

        return cls(
            chunk_id=chunk_id,
            text=full_text,
            source_url=source_url,
            page_title=page_title,
            heading_path=heading_path,
            heading_parts=heading_parts,
            heading_level=heading_level,
            source_type=source_type,
            section=section,
            token_count=token_count,
            breadcrumb_tokens=breadcrumb_tok,
            file_path=file_path,
            chunk_index=chunk_index,
        )


def build_chunk_id(file_path: str, heading_path: str, chunk_index: int) -> str:
    """Deterministic 12-char hex ID (48-bit hash space).

    Same inputs always produce the same ID, so re-running the pipeline
    is safe — IDs stay stable, FAISS index can be rebuilt in-place.

    Collision risk: 48 bits gives ~1-in-10^9 collision chance at 2000 chunks
    (birthday bound: sqrt(2^48) ≈ 16M). Negligible for our corpus size.
    """
    raw = f"{file_path}|{heading_path}|{chunk_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def estimate_tokens(text: str) -> int:
    """Quick token count estimate: word_count * 1.3, rounded.

    Accurate enough for prompt budget math. We're not doing exact
    billing — just need to know if a chunk is ~300 or ~800 tokens.
    """
    if not text:
        return 0
    words = len(text.split())
    return round(words * _WORD_TO_TOKEN_RATIO)


def _build_breadcrumb(page_title: str, heading_path: str) -> str:
    """Combine page title and heading hierarchy into a breadcrumb string.

    Example: page_title="GitLab Values", heading_path="Collaboration > Kindness"
    → "GitLab Values > Collaboration > Kindness"

    If heading_path is empty (chunk covers the whole page intro),
    just returns the page title.
    """
    if not page_title and not heading_path:
        return ""
    if not heading_path:
        return page_title
    if not page_title:
        return heading_path
    return f"{page_title} > {heading_path}"
