from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from src.config import GRAPH_PATH
from src.models import GraphFact


def _as_fact(edge: Dict[str, Any]) -> GraphFact:
    return GraphFact(
        subject=edge["source"],
        relationship=edge.get("relationship", "RELATED_TO"),
        object=edge["target"],
        source=edge.get("source_doc") or "derived graph",
        properties={key: value for key, value in edge.items() if key not in {"source", "target", "relationship"}},
    )


@lru_cache(maxsize=1)
def load_graph() -> Dict[str, Any]:
    try:
        return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        from knowledge_graph.build_graph import build_graph

        return build_graph()


def _nodes_by_id() -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in load_graph()["nodes"]}


def _edges() -> List[Dict[str, Any]]:
    return load_graph()["edges"]


def _edge_facts(subject: Optional[str] = None, relationship: Optional[str] = None, target: Optional[str] = None) -> List[GraphFact]:
    facts: List[GraphFact] = []
    for edge in _edges():
        if subject and edge["source"] != subject:
            continue
        if relationship and edge.get("relationship") != relationship:
            continue
        if target and edge["target"] != target:
            continue
        facts.append(_as_fact(edge))
    return facts


def _extract_amount(question: str) -> Optional[int]:
    match = re.search(r"(?:₹|rs\.?|inr)?\s*([\d,]{2,})(?:\s*(?:rupees|inr))?", question.lower())
    if not match:
        return None
    amount = int(match.group(1).replace(",", ""))
    prefix = question.lower()[max(0, match.start() - 24) : match.start()]
    if any(term in prefix for term in ["above", "over", "more than", "greater than", ">"]):
        return amount + 1
    return amount


def _extract_delay_hours(question: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[- ]?(?:hours?|hrs?)", question.lower())
    if match:
        return float(match.group(1))
    match = re.search(r"(?:over|above|more than|after)\s+(\d+(?:\.\d+)?)", question.lower())
    if match:
        return float(match.group(1)) + 0.001
    return None


def _extract_sku(question: str) -> Optional[str]:
    match = re.search(r"\b[A-Z]{3,5}-[A-Z0-9-]+\b", question)
    return match.group(0) if match else None


def _match_kpi_name(question: str) -> Optional[str]:
    normalized = question.lower()
    aliases = {
        "inventory aging": "Inventory Aging",
        "slow-moving": "Slow-Moving Inventory",
        "slow moving": "Slow-Moving Inventory",
        "reorder level": "Reorder Level",
        "stockout risk": "Stockout Risk",
        "sell-through": "Sell-Through Rate",
        "sell through": "Sell-Through Rate",
        "dead stock": "Dead Stock",
        "dead-stock": "Dead Stock",
    }
    for alias, kpi in aliases.items():
        if alias in normalized:
            return kpi
    return None


def find_procurement_approver(amount_inr: int) -> Dict[str, Any]:
    if amount_inr <= 25000:
        threshold = "Procurement Request Up to ₹25,000"
        approver = "Team Lead"
    elif amount_inr <= 100000:
        threshold = "Procurement Request ₹25,001 to ₹1,00,000"
        approver = "Department Head"
    elif amount_inr <= 500000:
        threshold = "Procurement Request ₹1,00,001 to ₹5,00,000"
        approver = "Finance Manager"
    elif amount_inr <= 1500000:
        threshold = "Procurement Request ₹5,00,001 to ₹15,00,000"
        approver = "CFO"
    else:
        threshold = "Procurement Request Above ₹15,00,000"
        approver = "COO and CFO"

    facts = _edge_facts(subject=threshold, relationship="REQUIRES_APPROVAL_FROM")
    return {
        "amount_inr": amount_inr,
        "threshold": threshold,
        "required_approver": approver,
        "source_document": "procurement_approval_policy.md",
        "graph_facts": facts,
    }


def find_delay_escalation(
    delay_hours: float,
    is_critical_account: bool = False,
    order_value_inr: Optional[int] = None,
) -> Dict[str, Any]:
    if delay_hours < 6:
        severity = "Severity 0"
    elif delay_hours < 12:
        severity = "Severity 1"
    elif delay_hours < 24:
        severity = "Severity 2"
    elif delay_hours < 48:
        severity = "Severity 3"
    else:
        severity = "Severity 4"

    node = _nodes_by_id().get(severity, {})
    facts = _edge_facts(subject=severity)
    if delay_hours > 72 or is_critical_account or (order_value_inr and order_value_inr > 250000):
        facts.extend(_edge_facts(subject="Severity 4", target="Shipment Delay Escalation SOP"))
    return {
        "delay_hours": delay_hours,
        "severity": severity,
        "classification": node.get("classification"),
        "communication_requirement": node.get("communication_requirement"),
        "source_document": "shipment_escalation_sop.md",
        "graph_facts": facts,
    }


def find_kpi_relationship(kpi_name: str) -> Dict[str, Any]:
    nodes = _nodes_by_id()
    if kpi_name not in nodes:
        return {"kpi": kpi_name, "found": False, "graph_facts": []}
    facts = _edge_facts(subject=kpi_name)
    node = nodes[kpi_name]
    return {
        "kpi": kpi_name,
        "found": True,
        "formula": node.get("formula"),
        "columns": node.get("columns", []),
        "source_document": "inventory_kpi_guide.md",
        "graph_facts": facts,
    }


def find_sku_relationship(sku: str) -> Dict[str, Any]:
    nodes = _nodes_by_id()
    if sku not in nodes:
        return {"sku": sku, "found": False, "graph_facts": []}
    facts = _edge_facts(subject=sku)
    node = nodes[sku]
    return {
        "sku": sku,
        "found": True,
        "properties": node,
        "branch": node.get("branch"),
        "category": node.get("category"),
        "supplier": node.get("preferred_supplier"),
        "graph_facts": facts,
    }


def get_related_documents(entity_name: str) -> List[str]:
    normalized = entity_name.lower()
    documents = set()
    for edge in _edges():
        if normalized in edge["source"].lower() or normalized in edge["target"].lower():
            source = edge.get("source_doc")
            if source and source.endswith((".md", ".csv")):
                documents.add(source)

    direct = {
        "service credit": ["shipment_escalation_sop.md", "customer_communication_playbook.md"],
        "refund": ["customer_communication_playbook.md", "shipment_escalation_sop.md"],
        "procurement": ["procurement_approval_policy.md"],
        "inventory aging": ["inventory_kpi_guide.md"],
        "stockout risk": ["inventory_kpi_guide.md"],
        "shipment delay": ["shipment_escalation_sop.md", "customer_communication_playbook.md"],
    }
    for key, values in direct.items():
        if key in normalized:
            documents.update(values)
    return sorted(documents)


def graph_facts_for_question(question: str) -> List[GraphFact]:
    normalized = question.lower()
    facts: List[GraphFact] = []

    amount = _extract_amount(question)
    if amount is not None and ("approval" in normalized or "approve" in normalized or "approver" in normalized):
        facts.extend(find_procurement_approver(amount)["graph_facts"])

    delay_hours = _extract_delay_hours(question)
    if delay_hours is not None and ("delay" in normalized or "shipment" in normalized):
        facts.extend(find_delay_escalation(delay_hours)["graph_facts"])

    sku = _extract_sku(question)
    if sku:
        facts.extend(find_sku_relationship(sku)["graph_facts"])

    kpi = _match_kpi_name(question)
    if kpi:
        facts.extend(find_kpi_relationship(kpi)["graph_facts"])

    if (not facts and "refund" in normalized) or "service credit" in normalized:
        facts.extend(_edge_facts(target="Service Credit"))

    seen = set()
    deduped: List[GraphFact] = []
    for fact in facts:
        key = (fact.subject, fact.relationship, fact.object, fact.source)
        if key not in seen:
            seen.add(key)
            deduped.append(fact)
    return deduped


def expand_query_with_graph(question: str) -> str:
    additions: List[str] = []
    facts = graph_facts_for_question(question)
    for fact in facts[:8]:
        additions.extend([fact.subject, fact.relationship, fact.object])

    amount = _extract_amount(question)
    if amount is not None:
        result = find_procurement_approver(amount)
        additions.extend([result["threshold"], result["required_approver"], "Approval Threshold Matrix"])

    delay_hours = _extract_delay_hours(question)
    if delay_hours is not None:
        result = find_delay_escalation(delay_hours)
        additions.extend([result["severity"], str(result.get("classification")), "Escalation Timeline"])

    kpi = _match_kpi_name(question)
    if kpi:
        result = find_kpi_relationship(kpi)
        additions.extend([kpi, *result.get("columns", []), "KPI Summary Table"])

    related_docs = get_related_documents(question)
    additions.extend(related_docs)

    if not additions:
        return question
    return question + " " + " ".join(str(item) for item in additions if item)
