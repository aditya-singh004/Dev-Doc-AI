"""Benchmark keyword retrieval against the app's RAG retriever."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.rag_service import RAGService


CASES_PATH = Path(__file__).with_name("retrieval_eval_cases.json")
DOCS_DIR = REPO_ROOT / "docs"
TOKEN_RE = re.compile(r"[a-z0-9_]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate source-level retrieval hit rate for the DDA docs."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=CASES_PATH,
        help="Path to the benchmark cases JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the evaluation summary as JSON.",
    )
    return parser.parse_args()


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def load_cases(path: Path) -> List[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_doc_texts() -> Dict[str, str]:
    docs: Dict[str, str] = {}
    for path in sorted(DOCS_DIR.glob("*.md")):
        docs[path.name] = path.read_text(encoding="utf-8")
    if not docs:
        raise FileNotFoundError(f"No markdown docs found in {DOCS_DIR}")
    return docs


def build_keyword_index(doc_texts: Dict[str, str]) -> tuple[Dict[str, Counter], Dict[str, float]]:
    doc_counters: Dict[str, Counter] = {}
    doc_freq: Counter = Counter()

    for name, text in doc_texts.items():
        counts = Counter(tokenize(text))
        doc_counters[name] = counts
        for token in counts:
            doc_freq[token] += 1

    total_docs = len(doc_counters)
    idf = {
        token: math.log((1 + total_docs) / (1 + freq)) + 1.0
        for token, freq in doc_freq.items()
    }
    return doc_counters, idf


def keyword_rank(
    query: str, doc_counters: Dict[str, Counter], idf: Dict[str, float]
) -> List[str]:
    query_counts = Counter(tokenize(query))
    scored: List[tuple[float, str]] = []

    for name, counts in doc_counters.items():
        score = 0.0
        for token, qtf in query_counts.items():
            dtf = counts.get(token, 0)
            if not dtf:
                continue
            score += qtf * math.log1p(dtf) * idf.get(token, 0.0)
        scored.append((score, name))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored]


def dedupe_preserve_order(values: Sequence[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def rank_for_expected(ranked: Sequence[str], expected: Sequence[str]) -> int | None:
    expected_set = set(expected)
    for idx, item in enumerate(ranked, start=1):
        if item in expected_set:
            return idx
    return None


async def rag_rank(service: RAGService, query: str) -> tuple[List[str], float]:
    started = time.perf_counter()
    _, sources = await service.retrieve(query)
    elapsed_ms = (time.perf_counter() - started) * 1000
    ranked = dedupe_preserve_order([source.source for source in sources])
    return ranked, elapsed_ms


async def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases)
    doc_texts = load_doc_texts()
    doc_counters, idf = build_keyword_index(doc_texts)

    service = RAGService()
    if not service.initialize():
        raise RuntimeError("Failed to initialize RAGService. Check local index and env.")

    results = []
    rag_hits_top1 = 0
    baseline_hits_top1 = 0
    rag_mrr = 0.0
    baseline_mrr = 0.0
    rag_latency_total_ms = 0.0

    for case in cases:
        expected_sources = case["expected_sources"]
        baseline_sources = keyword_rank(case["query"], doc_counters, idf)
        rag_sources, rag_latency_ms = await rag_rank(service, case["query"])

        baseline_rank_value = rank_for_expected(baseline_sources, expected_sources)
        rag_rank_value = rank_for_expected(rag_sources, expected_sources)

        if baseline_rank_value == 1:
            baseline_hits_top1 += 1
        if rag_rank_value == 1:
            rag_hits_top1 += 1

        if baseline_rank_value is not None:
            baseline_mrr += 1.0 / baseline_rank_value
        if rag_rank_value is not None:
            rag_mrr += 1.0 / rag_rank_value

        rag_latency_total_ms += rag_latency_ms
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_sources": expected_sources,
                "baseline_sources": baseline_sources,
                "baseline_rank": baseline_rank_value,
                "rag_sources": rag_sources,
                "rag_rank": rag_rank_value,
                "rag_latency_ms": round(rag_latency_ms, 2),
            }
        )

    total_cases = len(cases)
    baseline_top1 = baseline_hits_top1 / total_cases
    rag_top1 = rag_hits_top1 / total_cases
    baseline_mrr /= total_cases
    rag_mrr /= total_cases
    avg_rag_latency_ms = rag_latency_total_ms / total_cases
    abs_gain_points = (rag_top1 - baseline_top1) * 100
    rel_gain_pct = (
        ((rag_top1 - baseline_top1) / baseline_top1) * 100 if baseline_top1 else None
    )

    summary = {
        "total_cases": total_cases,
        "baseline_top1_hit_rate": round(baseline_top1, 4),
        "rag_top1_hit_rate": round(rag_top1, 4),
        "baseline_mrr": round(baseline_mrr, 4),
        "rag_mrr": round(rag_mrr, 4),
        "avg_rag_latency_ms": round(avg_rag_latency_ms, 2),
        "absolute_gain_points": round(abs_gain_points, 2),
        "relative_gain_pct": round(rel_gain_pct, 2) if rel_gain_pct is not None else None,
        "results": results,
    }

    print(
        "Top-1 hit rate: baseline {0:.1f}% -> RAG {1:.1f}% ({2:+.1f} pts)".format(
            baseline_top1 * 100, rag_top1 * 100, abs_gain_points
        )
    )
    if rel_gain_pct is not None:
        print(f"Relative improvement: {rel_gain_pct:.1f}%")
    print(
        "MRR: baseline {0:.3f} -> RAG {1:.3f}".format(
            baseline_mrr, rag_mrr
        )
    )
    print(f"Average RAG retrieval latency: {avg_rag_latency_ms:.2f} ms")
    print()
    print("Case-by-case ranks:")
    for result in results:
        print(
            "- {id}: baseline rank {baseline_rank}, RAG rank {rag_rank}, expected {expected}".format(
                id=result["id"],
                baseline_rank=result["baseline_rank"],
                rag_rank=result["rag_rank"],
                expected=", ".join(result["expected_sources"]),
            )
        )

    if args.output is not None:
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print()
        print(f"Wrote JSON summary to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
