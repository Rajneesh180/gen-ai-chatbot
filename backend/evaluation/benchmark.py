"""Offline evaluation harness for the RAG pipeline.

Runs a set of benchmark questions through the full pipeline and scores
retrieval relevance + answer quality.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import yaml

from backend.config import DATA_DIR
from backend.rag.generator import generate
from backend.rag.prompt import build_prompt
from backend.retrieval.hybrid import retrieve

QUESTIONS_PATH = Path(__file__).parent / "questions.yaml"
RESULTS_PATH = DATA_DIR / "eval_results.json"


def load_questions() -> List[Dict[str, Any]]:
    """Load benchmark questions from YAML file."""
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("questions", [])


def run_benchmark(questions: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """Run each question through retrieve → prompt → generate and collect results."""
    if questions is None:
        questions = load_questions()

    results: List[Dict[str, Any]] = []
    total = len(questions)

    for i, q in enumerate(questions, 1):
        query = q["question"]
        expected_topic = q.get("expected_topic", "")

        print(f"[EVAL] {i}/{total}: {query[:80]}...")

        t0 = time.time()
        chunks = retrieve(query)
        retrieval_time = time.time() - t0

        prompt = build_prompt(query, chunks)

        t0 = time.time()
        answer = generate(prompt)
        generation_time = time.time() - t0

        result = {
            "question": query,
            "expected_topic": expected_topic,
            "answer": answer,
            "sources": [c.get("source_url", "") for c in chunks],
            "retrieval_time_s": round(retrieval_time, 2),
            "generation_time_s": round(generation_time, 2),
            "num_chunks": len(chunks),
        }
        results.append(result)

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[EVAL] Done — {len(results)} results saved to {RESULTS_PATH}")
    return results
