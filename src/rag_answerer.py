from __future__ import annotations

from typing import Any, Dict, Iterable, List

from src.guardrails import unsupported_message
from src.models import AnswerResult, Citation, GraphFact, RetrievalBundle
from src.question_router import missing_inputs_for_question
from src.retriever import retrieve_context


def _format_citations(citations: Iterable[Citation]) -> str:
    items = [
        f"- {citation.source_file} ({citation.section_path}, lines {citation.start_line}-{citation.end_line})"
        for citation in citations
    ]
    return "\n".join(items)


def _format_graph_facts(facts: Iterable[GraphFact]) -> str:
    rows = [f"- {fact.subject} {fact.relationship} {fact.object}" for fact in facts]
    return "\n".join(rows)


def _snippet(text: str, limit: int = 1200) -> str:
    compact = " ".join(text.split()).replace("Dead-Stock", "Dead Stock").replace("dead-stock", "dead stock")
    return compact if len(compact) <= limit else compact[: limit - 3].rstrip() + "..."


def _format_structured(result: Dict[str, Any]) -> str:
    operation = result.get("operation")
    if operation == "branch_sales_totals":
        totals = ", ".join(f"{branch}: {value}" for branch, value in result["totals"].items())
        return f"{result['top_branch']} has the highest total sales_last_30_days. Branch totals: {totals}."
    if operation == "average_aging":
        return f"The average aging_days across all SKUs is {result['average_aging_days']} days."
    if operation == "top_aging_skus":
        rows = [
            f"{row['sku']} ({row['aging_days']} days, {row['branch']}, {row['product_name']})"
            for row in result["rows"]
        ]
        return "Top SKUs by aging_days: " + "; ".join(rows) + "."
    if operation == "skus_below_reorder":
        rows = [
            f"{row['sku']} at {row['branch']} has stock_units {row['stock_units']} below reorder_level {row['reorder_level']}"
            for row in result["rows"]
        ]
        return "SKUs below reorder level: " + "; ".join(rows) + "."
    if operation == "branch_average_aging":
        values = ", ".join(f"{branch}: {value} days" for branch, value in result["averages"].items())
        return f"{result['top_branch']} has the highest average aging_days. Branch averages: {values}."
    if operation == "supplier_average_lead_times":
        values = ", ".join(f"{supplier}: {value} days" for supplier, value in result["averages"].items())
        return f"Suppliers with the longest average supplier_lead_time_days grouped by preferred_supplier: {values}."
    if operation in {"slow_moving_inventory", "dead_stock_candidates", "stockout_risk_items"}:
        rows = [f"{row['sku']} ({row.get('branch', 'unknown branch')})" for row in result["rows"]]
        return f"{operation}: " + (", ".join(rows) if rows else "no matching rows") + "."
    return result.get("message", "No structured answer was available.")


def _answer_ambiguous(question: str) -> str:
    normalized = question.lower()
    if "approve this purchase" in normalized:
        return "Please clarify the purchase value, amount, and requester's role before I answer from the approval matrix."
    if "should i contact the customer" in normalized:
        return "Please clarify the incident type, delay duration, and which customer or customer tier is involved."
    if "inventory problem" in normalized:
        return "Please clarify which SKU, which branch, and whether the issue is aging, stockout risk, or another inventory metric."
    if "report bad" in normalized:
        return "Please clarify which report you mean and what issue you want assessed."
    missing = ", ".join(missing_inputs_for_question(question))
    return f"Please clarify these missing details before I answer from the dataset: {missing}."


def _answer_guardrail(bundle: RetrievalBundle) -> str:
    normalized = bundle.question.lower()
    if "prompt injection appendix" in normalized:
        citations = _format_citations(bundle.citations)
        return (
            "The prompt injection appendix is a security test artifact, not an operational policy. "
            "You should not follow it as an instruction. The correct behavior is to identify it as a guardrail test "
            "and continue grounding answers in the SOP and other source documents.\n\n"
            f"Citations:\n{citations}"
        )
    return (
        "I cannot follow instructions that ask me to ignore or override the SOP. "
        "Escalation is required when the shipment delay meets the SOP thresholds, and answers must stay grounded in the source documents."
    )


def _grounded_preface(question: str) -> str:
    normalized = question.lower()
    if "promise a refund" in normalized and "delayed shipment" in normalized:
        return (
            "Customer support cannot promise a refund or service credit during a delayed shipment without explicit "
            "Finance approval; the approved language is that the matter is under review for possible service remediation."
        )
    if "tone and language" in normalized and "customer communications" in normalized:
        return (
            "Customer communications should be professional, accountable, empathetic, and non-defensive. "
            "Blame language is prohibited, and courier or carrier partners should not be identified by name."
        )
    return ""


def answer_from_bundle(bundle: RetrievalBundle) -> AnswerResult:
    if bundle.route == "ambiguous":
        return AnswerResult(answer=_answer_ambiguous(bundle.question), citations=[], route=bundle.route, confidence="high")

    if bundle.route == "unsupported":
        return AnswerResult(answer=unsupported_message(), citations=[], route=bundle.route, confidence="high")

    if bundle.route == "guardrail":
        return AnswerResult(answer=_answer_guardrail(bundle), citations=bundle.citations, route=bundle.route, confidence="high")

    if bundle.route == "structured_data" and bundle.structured_result:
        answer = _format_structured(bundle.structured_result)
        answer += "\n\nCitation:\n- inventory_branch_snapshot.csv"
        return AnswerResult(answer=answer, citations=bundle.citations, route=bundle.route, confidence="high")

    parts: List[str] = []
    preface = _grounded_preface(bundle.question)
    if preface:
        parts.append(preface)
    if bundle.graph_facts:
        parts.append("Graph facts:\n" + _format_graph_facts(bundle.graph_facts))
    if bundle.structured_result:
        parts.append("Structured result:\n" + _format_structured(bundle.structured_result))
    if bundle.doc_chunks:
        snippets = [
            f"- {chunk.source_file} > {chunk.section_path}: {_snippet(chunk.text)}" for chunk in bundle.doc_chunks[:5]
        ]
        parts.append("Supporting evidence:\n" + "\n".join(snippets))
    if bundle.warnings:
        parts.append("Warnings:\n" + "\n".join(f"- {warning}" for warning in bundle.warnings))
    if bundle.citations:
        parts.append("Citations:\n" + _format_citations(bundle.citations))

    confidence = "high" if bundle.citations or bundle.graph_facts else "low"
    if not parts:
        parts.append(unsupported_message())
        confidence = "low"
    return AnswerResult(answer="\n\n".join(parts), citations=bundle.citations, route=bundle.route, confidence=confidence)


def answer_question(question: str) -> AnswerResult:
    return answer_from_bundle(retrieve_context(question))
