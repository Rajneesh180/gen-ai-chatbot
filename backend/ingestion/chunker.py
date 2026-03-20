"""
Heading-aware markdown chunker with paragraph-split fallback and overlap stitching.

This is the "chunk" stage of the pipeline. Takes MarkdownDocument objects from
md_loader and produces Chunk objects (schema.py) by splitting on heading
boundaries, applying size guards, merging tiny fragments, and stitching
40-token overlap between sibling chunks.

Pure function: stateless, no I/O, no side-effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from backend.ingestion.md_loader import MarkdownDocument, map_file_path_to_url
from backend.ingestion.schema import Chunk, estimate_tokens

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

TARGET_MIN_TOKENS = 350        # ideal lower bound per chunk
TARGET_MAX_TOKENS = 500        # ideal upper bound per chunk
HARD_CAP_TOKENS = 700          # above this → must split
MERGE_THRESHOLD_TOKENS = 50    # below this → merge with neighbor
OVERLAP_TOKENS = 40            # tail tokens prepended to next sibling

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# ATX headings: ## through ##### (skip H1 = page title, H6 = unused)
_HEADING_RE = re.compile(r"^(#{2,5})\s+(.+)$", re.MULTILINE)

# Fenced code blocks: ``` or ~~~, optionally with language tag
_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})", re.MULTILINE)

# HTML comments
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Triple+ blank lines → double
_EXCESS_BLANKS_RE = re.compile(r"\n{3,}")

# Sentence boundary: period + space + uppercase letter, or period + newline
_SENTENCE_RE = re.compile(r"(?<=\.)\s+(?=[A-Z])")


# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------

@dataclass
class _RawSection:
    """One heading + its content, before size evaluation."""
    level: int          # 2-5, or 1 for preamble
    heading_text: str   # "" for preamble
    body: str           # content under this heading (no sub-headings split yet)
    heading_path: str   # "Collaboration > Kindness"
    heading_parts: Tuple[str, ...]  # ("Collaboration", "Kindness")


# ---------------------------------------------------------------------------
# Markdown cleaning (applied per-section)
# ---------------------------------------------------------------------------

def _clean_body(text: str) -> str:
    """Light cleaning before token estimation and emission."""
    text = _HTML_COMMENT_RE.sub("", text)
    text = _EXCESS_BLANKS_RE.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Code fence detection
# ---------------------------------------------------------------------------

def _find_code_fence_ranges(body: str) -> List[Tuple[int, int]]:
    """Return (start, end) byte offsets of fenced code blocks.

    Handles both ``` and ~~~ fences. Unclosed fences extend to EOF.
    """
    ranges: List[Tuple[int, int]] = []
    fence_stack: Optional[int] = None  # start offset of opening fence

    for m in _CODE_FENCE_RE.finditer(body):
        if fence_stack is None:
            fence_stack = m.start()
        else:
            ranges.append((fence_stack, m.end()))
            fence_stack = None

    # unclosed fence → extends to end of document
    if fence_stack is not None:
        ranges.append((fence_stack, len(body)))

    return ranges


def _offset_in_code_fence(offset: int, ranges: List[Tuple[int, int]]) -> bool:
    """Check if a character offset falls inside any code fence range."""
    for start, end in ranges:
        if start <= offset < end:
            return True
    return False


# ---------------------------------------------------------------------------
# Step 1-2: Heading extraction + section building
# ---------------------------------------------------------------------------

def _extract_sections(body: str) -> List[_RawSection]:
    """Split document body into sections by heading boundaries.

    Returns an ordered list of _RawSection with heading hierarchy computed
    via a stack machine. Headings inside code fences are ignored.
    """
    code_ranges = _find_code_fence_ranges(body)

    # collect real heading positions (not inside code fences)
    headings: List[Tuple[int, int, int, str]] = []  # (start, end, level, text)
    for m in _HEADING_RE.finditer(body):
        if _offset_in_code_fence(m.start(), code_ranges):
            continue
        level = len(m.group(1))
        text = m.group(2).strip()
        headings.append((m.start(), m.end(), level, text))

    sections: List[_RawSection] = []
    stack: List[Tuple[int, str]] = []  # (level, text) for heading hierarchy

    # preamble: everything before the first heading
    if headings:
        preamble = body[: headings[0][0]].strip()
    else:
        preamble = body.strip()

    if preamble:
        sections.append(_RawSection(
            level=1,
            heading_text="",
            body=preamble,
            heading_path="",
            heading_parts=(),
        ))

    for i, (_h_start, h_end, level, text) in enumerate(headings):
        # extract content: from end of heading line to start of next heading
        if i + 1 < len(headings):
            content = body[h_end: headings[i + 1][0]]
        else:
            content = body[h_end:]

        content = content.strip()

        # stack machine → heading path
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))

        heading_path = " > ".join(t for _, t in stack)
        heading_parts = tuple(t for _, t in stack)

        sections.append(_RawSection(
            level=level,
            heading_text=text,
            body=content,
            heading_path=heading_path,
            heading_parts=heading_parts,
        ))

    return sections


# ---------------------------------------------------------------------------
# Step 5a: Paragraph-boundary splitting
# ---------------------------------------------------------------------------

def _split_paragraphs(text: str, target_max: int = TARGET_MAX_TOKENS) -> List[str]:
    """Split text on double-newline boundaries, grouping into ~target_max token chunks.

    Returns a list of text fragments. Single paragraphs exceeding target_max
    are returned whole (sentence splitting is the next fallback).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text] if text.strip() else []

    groups: List[str] = []
    current: List[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        if current and current_tokens + para_tokens > target_max:
            groups.append("\n\n".join(current))
            current = [para]
            current_tokens = para_tokens
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        groups.append("\n\n".join(current))

    return groups


# ---------------------------------------------------------------------------
# Step 5b: Sentence-boundary splitting (fallback)
# ---------------------------------------------------------------------------

def _split_sentences(text: str, target_max: int = TARGET_MAX_TOKENS) -> List[str]:
    """Split a single large paragraph on sentence boundaries."""
    sentences = _SENTENCE_RE.split(text)
    if len(sentences) <= 1:
        return [text]  # can't split further — return as-is

    groups: List[str] = []
    current: List[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = estimate_tokens(sent)
        if current and current_tokens + sent_tokens > target_max:
            groups.append(" ".join(current))
            current = [sent]
            current_tokens = sent_tokens
        else:
            current.append(sent)
            current_tokens += sent_tokens

    if current:
        groups.append(" ".join(current))

    return groups


# ---------------------------------------------------------------------------
# Step 4-5: Size evaluation + splitting
# ---------------------------------------------------------------------------

def _split_section(body: str) -> List[str]:
    """Split an oversized section body into sub-chunks.

    Tries paragraph boundaries first, then sentence boundaries as fallback.
    """
    # first pass: paragraph split
    parts = _split_paragraphs(body)

    # second pass: any part still over hard cap → sentence split
    result: List[str] = []
    for part in parts:
        if estimate_tokens(part) > HARD_CAP_TOKENS:
            result.extend(_split_sentences(part))
        else:
            result.append(part)

    return result


# ---------------------------------------------------------------------------
# Step 6: Merge tiny fragments
# ---------------------------------------------------------------------------

def _merge_tiny(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Absorb chunks under MERGE_THRESHOLD_TOKENS into their neighbors.

    Each dict has keys: content, heading_path, heading_parts, heading_level.
    Merges forward preferentially; merges backward for the last chunk.
    """
    if len(chunks) <= 1:
        return chunks

    merged: List[Dict[str, Any]] = []
    skip_next = False

    for i, chunk in enumerate(chunks):
        if skip_next:
            skip_next = False
            continue

        tokens = estimate_tokens(chunk["content"])

        if tokens < MERGE_THRESHOLD_TOKENS:
            if i + 1 < len(chunks):
                # merge forward
                next_c = chunks[i + 1]
                next_c["content"] = chunk["content"] + "\n\n" + next_c["content"]
                # keep next chunk's heading info (it's the "real" section)
                skip_next = False  # don't skip — let the merged next_c be processed normally
                chunks[i + 1] = next_c
                print(f"[CHUNK] MERGE  chunk {i} (<{MERGE_THRESHOLD_TOKENS} tokens, merged forward)")
                continue
            elif merged:
                # merge backward into previous
                merged[-1]["content"] = merged[-1]["content"] + "\n\n" + chunk["content"]
                print(f"[CHUNK] MERGE  chunk {i} (<{MERGE_THRESHOLD_TOKENS} tokens, merged backward)")
                continue

        merged.append(chunk)

    return merged


# ---------------------------------------------------------------------------
# Step 7: Overlap stitching
# ---------------------------------------------------------------------------

def _should_overlap(prev: Dict[str, Any], curr: Dict[str, Any]) -> bool:
    """True if curr should receive a 40-token tail from prev."""
    if prev["file_path"] != curr["file_path"]:
        return False
    # Case 1: paragraph-split fragments share the same heading_path
    if curr["heading_path"] == prev["heading_path"]:
        return True
    pp = prev["heading_parts"]
    cp = curr["heading_parts"]
    # Case 2: curr is a direct child of prev
    if len(cp) > len(pp) and cp[: len(pp)] == pp:
        return True
    # Case 3: siblings under the same parent heading
    if pp and cp and len(pp) == len(cp) and pp[:-1] == cp[:-1]:
        return True
    return False


def _apply_overlap(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stitch 40-token tails between eligible sibling chunks.

    Modifies chunk content in place. Does NOT change chunk identity fields.
    """
    overlap_count = 0

    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        curr = chunks[i]

        if not _should_overlap(prev, curr):
            continue

        prev_words = prev["content"].split()
        if len(prev_words) <= OVERLAP_TOKENS:
            continue  # prev too small to donate meaningful overlap

        tail_text = " ".join(prev_words[-OVERLAP_TOKENS:])
        curr["content"] = f"[...] {tail_text}\n\n{curr['content']}"
        overlap_count += 1

    return chunks


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def chunk_document(doc: MarkdownDocument) -> List[Chunk]:
    """Split a MarkdownDocument into a list of Chunk objects.

    This is the entry point called by the pipeline runner for each document.
    """
    source_url = map_file_path_to_url(doc.file_path, doc.source_type)
    body = _clean_body(doc.body)

    if not body:
        return []

    sections = _extract_sections(body)
    if not sections:
        return []

    # build intermediate chunk dicts (before merging/overlap)
    raw_chunks: List[Dict[str, Any]] = []

    for sec in sections:
        sec_body = _clean_body(sec.body)
        if not sec_body:
            continue

        # estimate tokens WITH breadcrumb to match what Chunk.from_raw_section does
        breadcrumb_est = estimate_tokens(doc.title)
        if sec.heading_path:
            breadcrumb_est += estimate_tokens(sec.heading_path)
        total_est = estimate_tokens(sec_body) + breadcrumb_est

        if total_est > HARD_CAP_TOKENS:
            # split into sub-chunks
            parts = _split_section(sec_body)
            for part in parts:
                if part.strip():
                    raw_chunks.append({
                        "content": part.strip(),
                        "heading_path": sec.heading_path,
                        "heading_parts": sec.heading_parts,
                        "heading_level": sec.level,
                        "file_path": doc.file_path,
                    })
        else:
            raw_chunks.append({
                "content": sec_body,
                "heading_path": sec.heading_path,
                "heading_parts": sec.heading_parts,
                "heading_level": sec.level,
                "file_path": doc.file_path,
            })

    if not raw_chunks:
        return []

    # merge tiny fragments
    raw_chunks = _merge_tiny(raw_chunks)

    # overlap stitching
    raw_chunks = _apply_overlap(raw_chunks)

    # emit Chunk objects
    chunks: List[Chunk] = []
    for idx, rc in enumerate(raw_chunks):
        chunk = Chunk.from_raw_section(
            content=rc["content"],
            file_path=doc.file_path,
            source_url=source_url,
            page_title=doc.title,
            heading_path=rc["heading_path"],
            heading_level=rc["heading_level"],
            source_type=doc.source_type,
            section=doc.section_slug,
            chunk_index=idx,
        )
        chunks.append(chunk)

    # per-file instrumentation
    total_tokens = sum(c.token_count for c in chunks)
    avg_tokens = total_tokens // len(chunks) if chunks else 0
    print(
        f"[CHUNK] {doc.file_path} -> {len(chunks)} chunks "
        f"({estimate_tokens(body)} -> {len(chunks)} x ~{avg_tokens} avg)"
    )

    return chunks


# ---------------------------------------------------------------------------
# Batch helper (for pipeline runner)
# ---------------------------------------------------------------------------

def chunk_all(docs: List[MarkdownDocument]) -> List[Chunk]:
    """Chunk an iterable of MarkdownDocuments and print summary stats.

    Returns a flat list of all Chunk objects across all documents.
    """
    all_chunks: List[Chunk] = []
    file_count = 0
    source_counts: Dict[str, Tuple[int, int]] = {}  # source_type -> (files, chunks)

    for doc in docs:
        file_count += 1
        doc_chunks = chunk_document(doc)

        st = doc.source_type
        f, c = source_counts.get(st, (0, 0))
        source_counts[st] = (f + 1, c + len(doc_chunks))

        all_chunks.extend(doc_chunks)

    if all_chunks:
        token_counts = [c.token_count for c in all_chunks]
        token_counts.sort()
        median_idx = len(token_counts) // 2
        median = token_counts[median_idx]

        overlap_count = sum(1 for c in all_chunks if "[...]" in c.text)

        print(f"[CHUNK] SUMMARY: {file_count} files -> {len(all_chunks)} chunks")
        for st, (f, c) in sorted(source_counts.items()):
            avg = round(c / f, 1) if f else 0
            print(f"  {st}: {f} files -> {c} chunks (avg {avg}/file)")
        print(
            f"  token range: min={min(token_counts)} max={max(token_counts)} "
            f"avg={sum(token_counts) // len(token_counts)} median={median}"
        )
        print(f"  overlapped pairs: {overlap_count}")
    else:
        print(f"[CHUNK] SUMMARY: {file_count} files -> 0 chunks")

    return all_chunks
