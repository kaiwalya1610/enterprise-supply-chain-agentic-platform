from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ranx import Qrels, Run, evaluate as evaluate_run

from src.models import RetrievalBundle
from src.rag_answerer import answer_from_bundle
from src.retriever import retrieve_context

try:
    from numba.core.errors import NumbaTypeSafetyWarning

    warnings.filterwarnings("ignore", category=NumbaTypeSafetyWarning, module="ranx")
except Exception:
    pass


EVAL_PATH = PROJECT_ROOT / "dataset" / "eval_questions.json"
DEFAULT_TOP_K = 6
RETRIEVAL_ELIGIBLE_TYPES = {"rag", "guardrail"}
RETRIEVAL_METRICS = [
    "hit_rate@1",
    "hit_rate@3",
    "hit_rate@6",
    "precision@1",
    "precision@3",
    "precision@6",
    "recall@1",
    "recall@3",
    "recall@6",
    "f1@6",
    "mrr@6",
    "map@6",
    "ndcg@6",
]


def _route_ok(expected_type: str, actual_route: str) -> bool:
    allowed = {
        "rag": {"rag_policy", "hybrid", "graph_lookup"},
        "structured_data": {"structured_data"},
        "ambiguous": {"ambiguous"},
        "unsupported": {"unsupported"},
        "guardrail": {"guardrail"},
    }
    return actual_route in allowed.get(expected_type, {expected_type})


def _citation_sources(result: Any) -> List[str]:
    return [citation.source_file for citation in result.citations]


def _unique_ordered(items: Iterable[str]) -> List[str]:
    seen = set()
    unique = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _retrieved_sources(bundle: RetrievalBundle, top_k: int) -> List[str]:
    return _unique_ordered(chunk.source_file for chunk in bundle.doc_chunks)[:top_k]


def _is_retrieval_eligible(item: Mapping[str, Any]) -> bool:
    return bool(item.get("expected_sources")) and item.get("question_type") in RETRIEVAL_ELIGIBLE_TYPES


def _rank_of_first_expected(retrieved_sources: Sequence[str], expected_sources: Sequence[str]) -> int | None:
    expected = set(expected_sources)
    for index, source in enumerate(retrieved_sources, start=1):
        if source in expected:
            return index
    return None


def _recall_at_k(retrieved_sources: Sequence[str], expected_sources: Sequence[str], top_k: int) -> float | None:
    if not expected_sources:
        return None
    retrieved = set(retrieved_sources[:top_k])
    expected = set(expected_sources)
    return len(retrieved & expected) / len(expected)


def build_qrels_and_run(rows: Sequence[Mapping[str, Any]]) -> tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, float]]]:
    qrels: Dict[str, Dict[str, int]] = {}
    run: Dict[str, Dict[str, float]] = {}

    for row in rows:
        if not row.get("retrieval_eligible"):
            continue

        qrels[row["id"]] = {source: 1 for source in row["expected_sources"]}
        run[row["id"]] = {
            source: 1.0 / rank
            for rank, source in enumerate(row["retrieved_sources"], start=1)
        }

    return qrels, run


def _empty_retrieval_metrics(metrics: Sequence[str]) -> Dict[str, float]:
    return {metric: 0.0 for metric in metrics}


def calculate_retrieval_metrics(
    rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[str] = RETRIEVAL_METRICS,
) -> Dict[str, float]:
    qrels_dict, run_dict = build_qrels_and_run(rows)
    if not qrels_dict:
        return _empty_retrieval_metrics(metrics)
    return dict(evaluate_run(Qrels(qrels_dict), Run(run_dict), metrics=list(metrics)))


def _rate(rows: Sequence[Mapping[str, Any]], key: str, predicate: Callable[[Mapping[str, Any]], bool] | None = None) -> float:
    selected = [row for row in rows if predicate(row)] if predicate else list(rows)
    if not selected:
        return 0.0
    return sum(1 for row in selected if row[key]) / len(selected)


def _summary_metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    return {
        "overall_pass_rate": _rate(rows, "passed"),
        "route_accuracy": _rate(rows, "route_pass"),
        "source_coverage": _rate(rows, "source_pass"),
        "must_contain_rate": _rate(rows, "terms_pass"),
        "clarification_accuracy": _rate(rows, "passed", lambda row: row["expected_type"] == "ambiguous"),
        "abstention_accuracy": _rate(rows, "passed", lambda row: row["expected_type"] == "unsupported"),
        "guardrail_accuracy": _rate(rows, "passed", lambda row: row["expected_type"] == "guardrail"),
        "structured_accuracy": _rate(rows, "passed", lambda row: row["expected_type"] == "structured_data"),
    }


def _evaluate_item(item: Mapping[str, Any], top_k: int) -> Dict[str, Any]:
    bundle = retrieve_context(item["question"])
    result = answer_from_bundle(bundle)
    answer_lower = result.answer.lower()
    citation_sources = _citation_sources(result)
    expected_sources = item.get("expected_sources", [])
    retrieved_sources = _retrieved_sources(bundle, top_k)

    route_pass = _route_ok(item["question_type"], result.route)
    source_pass = all(source in citation_sources for source in expected_sources)
    terms_pass = all(term.lower() in answer_lower for term in item.get("must_contain", []))
    ok = route_pass and source_pass and terms_pass

    return {
        "id": item["id"],
        "question": item["question"],
        "route": result.route,
        "expected_type": item["question_type"],
        "expected_sources": expected_sources,
        "retrieved_sources": retrieved_sources,
        "citation_sources": citation_sources,
        "sources": citation_sources,
        "route_pass": route_pass,
        "source_pass": source_pass,
        "terms_pass": terms_pass,
        "passed": ok,
        "retrieval_eligible": _is_retrieval_eligible(item),
        "retrieval_rank_of_first_expected": _rank_of_first_expected(retrieved_sources, expected_sources),
        "retrieval_recall_at_k": _recall_at_k(retrieved_sources, expected_sources, top_k),
        "answer": result.answer,
    }


def evaluate(top_k: int = DEFAULT_TOP_K) -> Dict[str, Any]:
    questions = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    rows = [_evaluate_item(item, top_k) for item in questions]
    passed = sum(1 for row in rows if row["passed"])
    retrieval_metrics = calculate_retrieval_metrics(rows)

    return {
        "passed": passed,
        "total": len(questions),
        "summary_metrics": _summary_metrics(rows),
        "retrieval_metrics": retrieval_metrics,
        "retrieval_eligible_total": sum(1 for row in rows if row["retrieval_eligible"]),
        "rows": rows,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate answer quality and retrieval accuracy.")
    parser.add_argument("--json-path", type=Path, help="Write the full evaluation report to this path.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Retrieval cutoff for per-row metrics.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = evaluate(top_k=args.top_k)
    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "total": report["total"],
                "summary_metrics": report["summary_metrics"],
                "retrieval_metrics": report["retrieval_metrics"],
                "retrieval_eligible_total": report["retrieval_eligible_total"],
            },
            indent=2,
        )
    )
    failures = [row for row in report["rows"] if not row["passed"]]
    for row in failures:
        print(f"\nFAIL {row['id']} route={row['route']} citations={row['citation_sources']}")
        print(f"retrieved_sources={row['retrieved_sources']}")
        print(f"route_pass={row['route_pass']} source_pass={row['source_pass']} terms_pass={row['terms_pass']}")
        print(row["answer"][:1000])
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
