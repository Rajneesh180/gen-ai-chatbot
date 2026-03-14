"""
Markdown file discovery, frontmatter parsing, and document loading.

This is the "walk" stage of the pipeline. It takes cloned repo directories,
finds all relevant .md files, parses their frontmatter, applies skip
heuristics, and yields MarkdownDocument objects for the chunker.

Does NOT do chunk splitting, embedding, or indexing.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple

import yaml

# -- Corpus filter config --------------------------------------------------

# Handbook dirs that are regulatory/governance noise, unlikely to show up
# in employee Q&A. See INGESTION_EXEC_SPEC Section 3 for rationale.
HANDBOOK_EXCLUDE_DIRS: Set[str] = {
    "board-meetings",
    "legal",
    "labor-and-employment-notices",
    "entity",
    "eba",
    "eta",
    "acquisitions",
    "resellers",
    "upstream-studios",
}

# Paths that signal archived/deprecated pages we don't want in the index.
_ARCHIVED_PATH_SEGMENTS = {"archive", "deprecated"}

# Files smaller than this after frontmatter stripping are too thin to chunk.
_MIN_BODY_BYTES = 100

# Frontmatter is bounded by opening/closing "---" lines.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Hugo shortcodes: {{< ... >}} and {{% ... %}}
_HUGO_SHORTCODE_RE = re.compile(r"\{\{[<%].*?[%>]\}\}", re.DOTALL)


# -- Data model -------------------------------------------------------------

@dataclass
class MarkdownDocument:
    """Raw parsed document ready for the chunker.

    One of these per accepted .md file. The chunker will split it into
    multiple Chunk objects based on heading boundaries.
    """

    file_path: str        # relative to repo root, e.g. "content/handbook/values/_index.md"
    source_type: str      # "handbook" or "direction"
    section_slug: str     # first dir after source root: "values", "engineering", etc.
    title: str            # from frontmatter, or filename fallback
    body: str             # markdown content with frontmatter stripped


# -- Frontmatter parsing ---------------------------------------------------

def parse_frontmatter(raw_text: str) -> Tuple[Dict, str]:
    """Split a markdown file into frontmatter dict and body text.

    Handles:
    - normal YAML frontmatter between --- delimiters
    - files with no frontmatter at all (returns empty dict)
    - malformed YAML (logs warning, returns empty dict)

    Returns (metadata_dict, body_text).
    """
    match = _FRONTMATTER_RE.match(raw_text)
    if not match:
        return {}, raw_text

    yaml_block = match.group(1)
    body = raw_text[match.end():]

    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        print(f"[WALK] WARN  malformed frontmatter, treating as no-frontmatter")
        return {}, raw_text

    if not isinstance(meta, dict):
        # YAML parsed to a scalar or list — not useful metadata
        return {}, raw_text

    return meta, body


# -- Skip heuristics -------------------------------------------------------

def _should_skip(
    file_path: str,
    meta: Dict,
    body: str,
    source_type: str,
    exclude_dirs: Set[str],
) -> Optional[str]:
    """Return a skip reason string, or None if the file should be accepted.

    Implements the 5 skip heuristics from the exec spec:
    1. redirect in frontmatter
    2. body too small
    3. excluded directory
    4. deprecated/archived status
    5. archived path segment
    """
    # 1 — redirect pages are stubs pointing elsewhere
    if meta.get("redirect_to") or meta.get("redirect"):
        return "SKIP_REDIRECT"

    # 2 — nearly empty pages (after frontmatter stripped)
    if len(body.encode("utf-8")) < _MIN_BODY_BYTES:
        return "SKIP_EMPTY"

    # 3 — directory exclusion list
    parts = Path(file_path).parts
    for part in parts:
        if part in exclude_dirs:
            return "SKIP_FILTER"

    # 4 — explicitly deprecated content
    status = meta.get("status", "").lower()
    if status in ("deprecated", "archived"):
        return "SKIP_DEPRECATED"

    # 5 — path-based archive detection
    lower_parts = {p.lower() for p in parts}
    if lower_parts & _ARCHIVED_PATH_SEGMENTS:
        return "SKIP_ARCHIVED_PATH"

    return None


# -- Section slug extraction ------------------------------------------------

def _extract_section(file_path: str, source_type: str) -> str:
    """Pull the top-level section from the file path.

    Handbook:  content/handbook/values/...       → "values"
    Direction: source/direction/create/...       → "create"
    TeamOps:   content/teamops/...               → "teamops"
    """
    parts = Path(file_path).parts

    if source_type == "handbook":
        # content / handbook / <section> / ...
        # content / teamops / <section> / ...
        if len(parts) > 1 and parts[0] == "content" and parts[1] in ("handbook", "teamops"):
            # len > 3 means there's a real sub-dir: content/handbook/values/_index.md
            # len == 3 means root page: content/teamops/_index.md → "teamops"
            return parts[2] if len(parts) > 3 else parts[1]
    elif source_type == "direction":
        # source / direction / <section> / ...
        if len(parts) > 2:
            return parts[2]

    return "unknown"


# -- Hugo shortcode stripping -----------------------------------------------

def _strip_hugo_shortcodes(text: str) -> str:
    """Remove Hugo template tags like {{< ref >}} and {{% alert %}}."""
    return _HUGO_SHORTCODE_RE.sub("", text)


# -- URL mapping stub -------------------------------------------------------

def map_file_path_to_url(file_path: str, source_type: str) -> str:
    """Convert a repo-relative file path to its public GitLab URL.

    Handbook:
        content/handbook/values/_index.md
        → https://handbook.gitlab.com/handbook/values/

    Direction:
        source/direction/create/_index.html.md.erb
        → https://about.gitlab.com/direction/create/

    This will be fully implemented in ingestion/url_mapper.py (Step 3).
    For now returns a best-effort URL so the rest of the pipeline
    can run end to end without blocking on this module.
    """
    if source_type == "handbook":
        # strip "content/" prefix, strip filename
        url_path = file_path.replace("content/", "", 1)
        # strip _index.md or similar filename
        url_path = re.sub(r"/[^/]*\.md$", "/", url_path)
        return f"https://handbook.gitlab.com/{url_path}"

    elif source_type == "direction":
        url_path = file_path.replace("source/", "", 1)
        url_path = re.sub(r"/[^/]*\.(md|html\.md|html\.md\.erb)$", "/", url_path)
        return f"https://about.gitlab.com/{url_path}"

    return ""


# -- Main discovery + loading -----------------------------------------------

def discover_markdown_files(
    repo_root: str,
    content_dir: str,
    source_type: str,
    extensions: Tuple[str, ...] = (".md",),
    exclude_dirs: Optional[Set[str]] = None,
) -> Generator[str, None, None]:
    """Yield repo-relative paths to .md files under content_dir, sorted.

    Walks the directory tree in deterministic order. Skips hidden dirs
    and .git. Uses a generator so we don't load the full path list into
    memory (though at ~600 files it wouldn't matter much).
    """
    if exclude_dirs is None:
        exclude_dirs = set()

    base = os.path.join(repo_root, content_dir)
    if not os.path.isdir(base):
        print(f"[WALK] WARN  content dir not found: {base}")
        return

    # os.walk with topdown=True so we can prune dirs in-place
    for dirpath, dirnames, filenames in os.walk(base, topdown=True):
        # prune hidden dirs and .git
        dirnames[:] = sorted(
            d for d in dirnames
            if not d.startswith(".") and d != ".git"
        )

        for fname in sorted(filenames):
            if any(fname.endswith(ext) for ext in extensions):
                abs_path = os.path.join(dirpath, fname)
                yield os.path.relpath(abs_path, repo_root)


def load_documents(
    repo_root: str,
    source_type: str,
    content_dir: str,
    extensions: Tuple[str, ...] = (".md",),
    exclude_dirs: Optional[Set[str]] = None,
) -> Generator[MarkdownDocument, None, None]:
    """Walk a repo subtree and yield parsed MarkdownDocument objects.

    This is the entry point the pipeline runner (run_ingest.py) will call.
    It handles discovery, frontmatter parsing, skip filtering, and
    hugo shortcode cleanup — everything before chunking.
    """
    if exclude_dirs is None:
        exclude_dirs = HANDBOOK_EXCLUDE_DIRS if source_type == "handbook" else set()

    accepted = 0
    skipped: Dict[str, int] = {}

    for rel_path in discover_markdown_files(
        repo_root, content_dir, source_type, extensions, exclude_dirs
    ):
        abs_path = os.path.join(repo_root, rel_path)

        try:
            raw = Path(abs_path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"[WALK] WARN  read error {rel_path}: {e}")
            continue

        meta, body = parse_frontmatter(raw)

        # strip hugo shortcodes (handbook uses these heavily)
        if source_type == "handbook":
            body = _strip_hugo_shortcodes(body)

        skip_reason = _should_skip(rel_path, meta, body, source_type, exclude_dirs)
        if skip_reason:
            skipped[skip_reason] = skipped.get(skip_reason, 0) + 1
            print(f"[WALK] {skip_reason}  {source_type}  {rel_path}")
            continue

        title = meta.get("title", "") or Path(rel_path).stem.replace("_", " ").title()
        section = _extract_section(rel_path, source_type)

        accepted += 1
        print(f"[WALK] ACCEPT  {source_type}  {rel_path}")

        yield MarkdownDocument(
            file_path=rel_path,
            source_type=source_type,
            section_slug=section,
            title=title,
            body=body,
        )

    # summary line — useful in pipeline logs
    total_skipped = sum(skipped.values())
    skip_detail = ", ".join(f"{k}: {v}" for k, v in sorted(skipped.items()))
    print(
        f"[WALK] {source_type} done — {accepted} accepted, "
        f"{total_skipped} skipped ({skip_detail or 'none'})"
    )
