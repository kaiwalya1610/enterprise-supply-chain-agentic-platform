from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, get_args

from src.models import Citation, GraphFact, RetrievalBundle, SourceChunk
from src.retriever import retrieve_parallel_context
from src.structured_data import (
    average_aging,
    branch_average_aging,
    branch_sales_totals,
    dead_stock_candidates,
    skus_below_reorder,
    slow_moving_inventory,
    stockout_risk_items,
    supplier_average_lead_times,
    top_aging_skus,
)


InventoryOperation = Literal[
    "branch_sales_totals",
    "average_aging",
    "top_aging_skus",
    "skus_below_reorder",
    "branch_average_aging",
    "supplier_average_lead_times",
    "slow_moving_inventory",
    "dead_stock_candidates",
    "stockout_risk_items",
]


def citation_to_dict(citation: Citation) -> Dict[str, Any]:
    return {
        "source_file": citation.source_file,
        "section_heading": citation.section_heading,
        "section_path": citation.section_path,
        "start_line": citation.start_line,
        "end_line": citation.end_line,
    }


def chunk_to_dict(chunk: SourceChunk) -> Dict[str, Any]:
    return {
        "id": chunk.id,
        "text": chunk.text,
        "source_file": chunk.source_file,
        "section_heading": chunk.section_heading,
        "section_path": chunk.section_path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "document_id": chunk.document_id,
        "security_test_artifact": chunk.security_test_artifact,
        "score": chunk.score,
        "similarity_score": chunk.similarity_score,
    }


def graph_fact_to_dict(fact: GraphFact) -> Dict[str, Any]:
    return {
        "subject": fact.subject,
        "relationship": fact.relationship,
        "object": fact.object,
        "source": fact.source,
        "subject_type": fact.subject_type,
        "object_type": fact.object_type,
        "properties": fact.properties,
    }


def retrieval_bundle_to_dict(bundle: RetrievalBundle, top_k: Optional[int] = None) -> Dict[str, Any]:
    chunks = bundle.doc_chunks[:top_k] if top_k else bundle.doc_chunks
    return {
        "question": bundle.question,
        "route": bundle.route,
        "doc_chunks": [chunk_to_dict(chunk) for chunk in chunks],
        "graph_facts": [graph_fact_to_dict(fact) for fact in bundle.graph_facts],
        "structured_result": bundle.structured_result,
        "citations": [citation_to_dict(citation) for citation in bundle.citations],
        "warnings": bundle.warnings,
    }


def retrieve_supply_chain_context(question: str, top_k: int = 6) -> Dict[str, Any]:
    """Return full abc.co retrieval context for a question."""
    safe_top_k = max(1, min(int(top_k), 12))
    bundle = retrieve_parallel_context(question, top_k=safe_top_k)
    return retrieval_bundle_to_dict(bundle, top_k=safe_top_k)


def analyze_inventory_snapshot(operation: InventoryOperation, limit: int = 5) -> Dict[str, Any]:
    """Run a deterministic pandas-backed operation over the inventory snapshot."""
    safe_limit = max(1, min(int(limit), 25))
    operations = {
        "branch_sales_totals": lambda: branch_sales_totals(),
        "average_aging": lambda: average_aging(),
        "top_aging_skus": lambda: top_aging_skus(safe_limit),
        "skus_below_reorder": lambda: skus_below_reorder(),
        "branch_average_aging": lambda: branch_average_aging(),
        "supplier_average_lead_times": lambda: supplier_average_lead_times(safe_limit),
        "slow_moving_inventory": lambda: slow_moving_inventory(),
        "dead_stock_candidates": lambda: dead_stock_candidates(),
        "stockout_risk_items": lambda: stockout_risk_items(),
    }
    if operation not in operations:
        allowed = ", ".join(get_args(InventoryOperation))
        return {
            "operation": "unsupported_inventory_operation",
            "message": f"Unsupported operation '{operation}'. Supported operations: {allowed}.",
        }
    return operations[operation]()


def inventory_operation_for_question(question: str) -> InventoryOperation:
    normalized = question.lower()
    if "highest total sales" in normalized or ("total sales" in normalized and "branch" in normalized):
        return "branch_sales_totals"
    if "average inventory aging across all" in normalized or "average aging across all" in normalized:
        return "average_aging"
    if "top 5" in normalized and ("aging" in normalized or "aging days" in normalized):
        return "top_aging_skus"
    if "below" in normalized and "reorder" in normalized:
        return "skus_below_reorder"
    if "highest average inventory aging" in normalized or (
        "average" in normalized and "aging" in normalized and "branch" in normalized
    ):
        return "branch_average_aging"
    if "supplier" in normalized and "lead time" in normalized:
        return "supplier_average_lead_times"
    if "slow-moving" in normalized or "slow moving" in normalized:
        return "slow_moving_inventory"
    if "dead-stock" in normalized or "dead stock" in normalized:
        return "dead_stock_candidates"
    if "stockout risk" in normalized:
        return "stockout_risk_items"
    return "average_aging"


def retrieved_text_for_guardrails(context: Dict[str, Any]) -> str:
    parts: List[str] = []
    for chunk in context.get("doc_chunks", []):
        parts.append(str(chunk.get("text", "")))
    graph_facts = context.get("graph_facts", [])
    if graph_facts:
        parts.extend(
            f"{fact.get('subject')} {fact.get('relationship')} {fact.get('object')}" for fact in graph_facts
        )
    structured_result = context.get("structured_result")
    if structured_result:
        parts.append(str(structured_result))
    return "\n".join(part for part in parts if part)
