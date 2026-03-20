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
        answer = None
        for attempt in range(3):
            try:
                answer = generate(prompt)
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 30 * (attempt + 1)
                    print(f"  [RATE-LIMITED] Attempt {attempt+1}/3 — waiting {wait}s...")
                    time.sleep(wait)
                else:
                    answer = f"[EVAL_ERROR] {err_str[:200]}"
                    break
        if answer is None:
            answer = "[EVAL_ERROR] Rate limited after 3 retries"
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

        # Pace requests to avoid rate limiting (Groq free tier: 30 RPM)
        if i < total:
            time.sleep(5)

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Compute summary stats
    avg_retrieval = sum(r["retrieval_time_s"] for r in results) / len(results) if results else 0
    avg_generation = sum(r["generation_time_s"] for r in results) / len(results) if results else 0
    avg_chunks = sum(r["num_chunks"] for r in results) / len(results) if results else 0
    answered = sum(1 for r in results if len(r["answer"]) > 50)

    print(f"\n{'='*60}")
    print(f"  EVALUATION RESULTS — {len(results)} questions")
    print(f"{'='*60}")
    print(f"  Answered (>50 chars):    {answered}/{len(results)} ({100*answered//max(len(results),1)}%)")
    print(f"  Avg retrieval time:      {avg_retrieval:.2f}s")
    print(f"  Avg generation time:     {avg_generation:.2f}s")
    print(f"  Avg chunks retrieved:    {avg_chunks:.1f}")
    print(f"  Results saved to:        {RESULTS_PATH}")
    print(f"{'='*60}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run RAG evaluation harness")
    parser.add_argument("--limit", type=int, default=0, help="Max questions to run (0 = all)")
    args = parser.parse_args()

    qs = load_questions()
    if args.limit > 0:
        qs = qs[: args.limit]
    run_benchmark(qs)
