"""CLI entry point for the ingestion pipeline.

Usage:
    python -m ingestion.run_ingest --all
    python -m ingestion.run_ingest --stage walk
    python -m ingestion.run_ingest --from chunk
    python -m ingestion.run_ingest --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List

from ingestion.chunker import chunk_all
from ingestion.md_loader import MarkdownDocument, load_documents

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path("data")
REPOS_DIR = DATA_DIR / "repos"

HANDBOOK_REPO = REPOS_DIR / "handbook"
DIRECTION_REPO = REPOS_DIR / "www-gitlab-com"

RAW_FILES_PATH = DATA_DIR / "raw_files.jsonl"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
FAISS_PATH = DATA_DIR / "faiss.index"
BM25_PATH = DATA_DIR / "bm25.pkl"
METADATA_PATH = DATA_DIR / "metadata.pkl"
VALIDATION_PATH = DATA_DIR / "validation_report.json"

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------
STAGE_ORDER = ["clone", "walk", "chunk", "embed", "index", "validate"]

# Each stage maps to the artifact(s) it requires from a previous stage.
PREREQUISITES = {
    "walk":     [HANDBOOK_REPO / ".git" / "HEAD", DIRECTION_REPO / ".git" / "HEAD"],
    "chunk":    [RAW_FILES_PATH],
    "embed":    [CHUNKS_PATH],
    "index":    [EMBEDDINGS_PATH, CHUNKS_PATH],
    "validate": [FAISS_PATH, BM25_PATH, METADATA_PATH],
}


def _check_prerequisites(stage: str) -> None:
    needed = PREREQUISITES.get(stage, [])
    for p in needed:
        if not p.exists():
            print(f"[ERROR] {p} not found. Run earlier stages first.")
            sys.exit(1)


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

CLONE_URLS = {
    "handbook": "https://gitlab.com/gitlab-com/content-sites/handbook.git",
    "www-gitlab-com": "https://gitlab.com/gitlab-com/www-gitlab-com.git",
}

CANARY_CHECKS = {
    "handbook": HANDBOOK_REPO / "content" / "handbook" / "values" / "_index.md",
    "www-gitlab-com": DIRECTION_REPO / "source" / "direction",
}


def run_clone() -> None:
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    for name, url in CLONE_URLS.items():
        dest = REPOS_DIR / name
        if (dest / ".git" / "HEAD").exists():
            print(f"[CLONE] pulling {name}...")
            subprocess.run(
                ["git", "-C", str(dest), "pull", "--ff-only"],
                check=True,
            )
        else:
            print(f"[CLONE] cloning {name} (shallow)...")
            subprocess.run(
                ["git", "clone", "--depth", "1", url, str(dest)],
                check=True,
            )

    # canary checks
    for name, canary in CANARY_CHECKS.items():
        if not canary.exists():
            print(f"[CLONE] ERROR  canary missing: {canary}")
            sys.exit(1)

    print("[CLONE] done — both repos ready.")


def run_walk() -> None:
    _check_prerequisites("walk")
    all_docs: List[MarkdownDocument] = []

    # handbook — main handbook tree
    all_docs.extend(load_documents(
        repo_root=str(HANDBOOK_REPO),
        source_type="handbook",
        content_dir="content/handbook",
    ))

    # handbook — teamops pages
    all_docs.extend(load_documents(
        repo_root=str(HANDBOOK_REPO),
        source_type="handbook",
        content_dir="content/teamops",
    ))

    # direction pages
    all_docs.extend(load_documents(
        repo_root=str(DIRECTION_REPO),
        source_type="direction",
        content_dir="source/direction",
        extensions=(".md", ".html.md", ".html.md.erb"),
    ))

    # write raw_files.jsonl
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_FILES_PATH, "w", encoding="utf-8") as f:
        for doc in all_docs:
            record = {
                "file_path": doc.file_path,
                "source_type": doc.source_type,
                "title": doc.title,
                "section": doc.section_slug,
                "body": doc.body,
                "source_url": "",  # filled by url_mapper if needed later
                "ingestion_method": "markdown",
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[WALK] wrote {len(all_docs)} records to {RAW_FILES_PATH}")


def _load_raw_files() -> List[MarkdownDocument]:
    """Read raw_files.jsonl back into MarkdownDocument objects."""
    docs: List[MarkdownDocument] = []
    with open(RAW_FILES_PATH, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            docs.append(MarkdownDocument(
                file_path=rec["file_path"],
                source_type=rec["source_type"],
                section_slug=rec.get("section", ""),
                title=rec.get("title", ""),
                body=rec["body"],
            ))
    return docs


def run_chunk() -> None:
    _check_prerequisites("chunk")

    docs = _load_raw_files()
    chunks = chunk_all(docs)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(c.to_json_line() + "\n")

    print(f"[CHUNK] wrote {len(chunks)} chunks to {CHUNKS_PATH}")


def run_embed() -> None:
    _check_prerequisites("embed")
    # TODO: implement once embedder.py is built
    print("[EMBED] not yet implemented — skipping")


def run_index() -> None:
    _check_prerequisites("index")
    # TODO: implement once indexer.py is built
    print("[INDEX] not yet implemented — skipping")


def run_validate() -> None:
    _check_prerequisites("validate")
    # TODO: implement once validator.py is built
    print("[VALIDATE] not yet implemented — skipping")


# ---------------------------------------------------------------------------
# Stage dispatch
# ---------------------------------------------------------------------------

STAGE_FUNCS = {
    "clone":    run_clone,
    "walk":     run_walk,
    "chunk":    run_chunk,
    "embed":    run_embed,
    "index":    run_index,
    "validate": run_validate,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GitLab Handbook/Direction ingestion pipeline",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run full pipeline")
    group.add_argument("--stage", choices=STAGE_ORDER, help="Run a single stage")
    group.add_argument(
        "--from", dest="from_stage", choices=STAGE_ORDER,
        help="Run from this stage onward",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Walk + chunk only (no API calls, no indexing)",
    )

    args = parser.parse_args()

    # resolve which stages to run
    if args.all:
        stages = list(STAGE_ORDER)
    elif args.stage:
        stages = [args.stage]
    else:
        start = STAGE_ORDER.index(args.from_stage)
        stages = STAGE_ORDER[start:]

    if args.dry_run:
        stages = [s for s in stages if s in ("clone", "walk", "chunk")]

    t0 = time.monotonic()
    for name in stages:
        print(f"\n{'=' * 50}")
        print(f"[{name.upper()}] Starting...")
        print(f"{'=' * 50}")
        stage_t0 = time.monotonic()
        STAGE_FUNCS[name]()
        elapsed = time.monotonic() - stage_t0
        print(f"[{name.upper()}] done in {elapsed:.1f}s")

    total = time.monotonic() - t0
    print(f"\nPipeline finished — {len(stages)} stage(s) in {total:.1f}s")


if __name__ == "__main__":
    main()
