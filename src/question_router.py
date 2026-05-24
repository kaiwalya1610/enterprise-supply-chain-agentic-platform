from __future__ import annotations

import re
from typing import List

from src.guardrails import detect_guardrail_route
from src.models import RouteDecision


STRUCTURED_TERMS = [
    "highest",
    "lowest",
    "average",
    "total",
    "top",
    "below reorder",
    "reorder level",
    "reorder point",
    "lead time",
    "lead times",
    "stockout",
    "dead-stock",
    "dead stock",
    "slow-moving",
    "slow moving",
]

POLICY_TERMS = [
    "process",
    "procedure",
    "policy",
    "policies",
    "explain",
    "what records",
    "tone",
    "language",
    "template",
    "three-quote",
    "emergency procurement",
    "refund",
    "credit",
]

GRAPH_TERMS = [
    "who approves",
    "approver",
    "who should be notified",
    "who handles",
    "responsible",
    "related",
    "supplier",
    "stocks",
    "stocked",
    "category",
    "which kpis",
    "which kpi",
]


def _has_amount(question: str) -> bool:
    return bool(re.search(r"(₹|rs\.?|inr)\s*[\d,]+|[\d,]+\s*(rupees|inr)", question.lower()))


def _has_delay_duration(question: str) -> bool:
    return bool(re.search(r"\b\d+\s*[- ]?(hour|hours|hr|hrs)\b|over\s+\d+|above\s+\d+|more than\s+\d+", question.lower()))


def _missing_inputs(question: str) -> List[str]:
    normalized = question.lower()
    missing: List[str] = []
    if "approve this purchase" in normalized or ("can i approve" in normalized and "purchase" in normalized):
        if not _has_amount(question):
            missing.append("purchase amount")
        missing.append("requester's role")
    if "should i contact the customer" in normalized:
        missing.extend(["incident type", "delay duration", "customer tier"])
    if "inventory problem serious" in normalized or "this inventory problem" in normalized:
        missing.extend(["SKU", "branch", "metric or issue"])
    if "report bad" in normalized:
        missing.extend(["which report", "what issue to evaluate"])
    return missing


def missing_inputs_for_question(question: str) -> List[str]:
    return _missing_inputs(question)


def route_question(question: str) -> RouteDecision:
    guardrail_route = detect_guardrail_route(question)
    if guardrail_route:
        return guardrail_route

    missing = _missing_inputs(question)
    if missing:
        return RouteDecision(
            route="ambiguous",
            reason="The question is missing inputs needed for a grounded answer.",
            required_inputs=missing,
        )

    normalized = question.lower()

    asks_about_prompt_appendix = "prompt injection appendix" in normalized
    if asks_about_prompt_appendix:
        return RouteDecision(route="guardrail", reason="Question asks about a known security test artifact.")

    is_inventory_data = (
        "inventory snapshot" in normalized
        or "snapshot" in normalized
        or "dataset" in normalized
        or "csv" in normalized
    )
    is_structured = is_inventory_data and any(term in normalized for term in STRUCTURED_TERMS)

    asks_approval = "approve" in normalized or "approval" in normalized or "approver" in normalized
    asks_delay_owner = ("delay" in normalized or "shipment" in normalized) and (
        "who" in normalized or "notified" in normalized or "after" in normalized or "over" in normalized
    )
    asks_kpi_relation = ("kpi" in normalized or "inventory aging" in normalized or "stockout risk" in normalized) and (
        "related" in normalized or "calculated" in normalized or "columns" in normalized
    )
    asks_sku_relation = bool(re.search(r"\b[A-Z]{3,5}-[A-Z0-9-]+\b", question)) and any(
        term in normalized for term in ["supplier", "branch", "category", "stocked", "relationship"]
    )

    if is_structured:
        return RouteDecision(route="structured_data", reason="Question requires deterministic CSV computation.")

    if asks_approval or asks_delay_owner or asks_kpi_relation:
        return RouteDecision(route="hybrid", reason="Question needs graph facts with source document support.")

    if asks_sku_relation or any(term in normalized for term in GRAPH_TERMS):
        return RouteDecision(route="graph_lookup", reason="Question asks for entity relationships.")

    if any(term in normalized for term in ["slow-moving", "slow moving", "kpi guide", "reorder level", "reorder point"]):
        return RouteDecision(route="rag_policy", reason="Question asks for an inventory KPI definition.")

    if any(term in normalized for term in POLICY_TERMS) or any(
        name in normalized
        for name in [
            "shipment",
            "procurement",
            "inventory aging",
            "customer communication",
            "service credit",
            "reorder level",
            "reorder point",
        ]
    ):
        return RouteDecision(route="rag_policy", reason="Question asks for policy or procedural text.")

    return RouteDecision(
        route="unsupported",
        reason="Question does not map to the supported dataset areas with enough specificity.",
    )
