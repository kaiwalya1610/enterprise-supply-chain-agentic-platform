from __future__ import annotations

from typing import Any, Dict


def _node(graph: Any, name: str, node_type: str, **properties: Any) -> None:
    graph.add_node(name, type=node_type, name=name, **properties)


def _edge(graph: Any, subject: str, relationship: str, obj: str, source: str, section: str, **props: Any) -> None:
    graph.add_edge(subject, obj, relationship=relationship, source_doc=source, section=section, **props)


PROCUREMENT_THRESHOLDS = [
    ("Procurement Request Up to ₹25,000", 0, 25000, "Team Lead"),
    ("Procurement Request ₹25,001 to ₹1,00,000", 25001, 100000, "Department Head"),
    ("Procurement Request ₹1,00,001 to ₹5,00,000", 100001, 500000, "Finance Manager"),
    ("Procurement Request ₹5,00,001 to ₹15,00,000", 500001, 1500000, "CFO"),
    ("Procurement Request Above ₹15,00,000", 1500001, None, "COO and CFO"),
]

DELAY_LEVELS = [
    ("Severity 0", 0, 5.999, "Operations Coordinator", "Monitor Only", "No proactive communication required"),
    ("Severity 1", 6, 11.999, "Operations Coordinator", "Operations Review", "No proactive communication unless customer inquires"),
    ("Severity 2", 12, 23.999, "Branch Operations Lead", "Branch Lead Notified", "Escalation ticket created; optional customer update"),
    ("Severity 3", 24, 47.999, "Logistics Manager", "Logistics Manager Notified", "Proactive customer update required"),
    ("Severity 4", 48, None, "Customer Success Manager and Logistics Manager", "Customer Success Escalation", "Formal written update required"),
]

KPI_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "Inventory Aging": {
        "columns": ["aging_days", "last_receipt_date"],
        "formula": "Current Date - Last Receipt Date",
        "owner": "Inventory Planning Team",
        "section": "Inventory Aging",
    },
    "Slow-Moving Inventory": {
        "columns": ["aging_days", "sales_last_30_days", "reserved_for_contract_customer"],
        "formula": "aging_days > 60 AND sales_last_30_days < 20",
        "owner": "Inventory Planning Team",
        "section": "Slow-Moving Inventory",
    },
    "Reorder Level": {
        "columns": ["stock_units", "reorder_level", "supplier_lead_time_days"],
        "formula": "Set per SKU per branch based on lead time, sales velocity, and safety stock",
        "owner": "Inventory Planning Team",
        "section": "Reorder Level",
    },
    "Stockout Risk": {
        "columns": ["stock_units", "reorder_level", "supplier_lead_time_days", "sales_last_30_days"],
        "formula": "stock_units <= reorder_level OR projected demand exceeds supply before lead time ends",
        "owner": "Inventory Planning Team + Operations",
        "section": "Stockout Risk",
    },
    "Sell-Through Rate": {
        "columns": ["sales_last_30_days", "stock_units"],
        "formula": "Units Sold / Units Received * 100",
        "owner": "Inventory Planning Team",
        "section": "Sell-Through Rate",
    },
    "Dead Stock": {
        "columns": ["aging_days", "sales_last_30_days"],
        "formula": "aging_days > 120 AND sales_last_30_days = 0",
        "owner": "Inventory Planning Team + Finance",
        "section": "Dead Stock",
    },
}


def add_document_graph(graph: Any) -> None:
    _add_documents(graph)
    _add_teams_and_roles(graph)
    _add_procurement(graph)
    _add_delay_escalation(graph)
    _add_customer_communication(graph)
    _add_kpis(graph)


def _add_documents(graph: Any) -> None:
    docs = {
        "Company Operations Background": "company_backdrop.md",
        "Shipment Delay Escalation SOP": "shipment_escalation_sop.md",
        "Procurement Approval Policy": "procurement_approval_policy.md",
        "Inventory KPI Guide": "inventory_kpi_guide.md",
        "Customer Communication Playbook": "customer_communication_playbook.md",
    }
    for title, source in docs.items():
        _node(graph, title, "Document", source_file=source)


def _add_teams_and_roles(graph: Any) -> None:
    source = "company_backdrop.md"
    section = "Core Teams"
    teams = {
        "Operations Team": ["Operations Coordinator", "Branch Operations Lead"],
        "Logistics Team": ["Logistics Manager"],
        "Procurement Team": ["Procurement Team"],
        "Inventory Planning Team": ["Inventory Planning Team"],
        "Customer Success Team": ["Customer Success Manager", "Account Manager"],
        "Finance Team": ["Finance Manager", "CFO"],
        "COO Office": ["COO"],
    }
    for team, roles in teams.items():
        _node(graph, team, "Team")
        _edge(graph, team, "DEFINED_IN", "Company Operations Background", source, section)
        for role in roles:
            _node(graph, role, "Role")
            _edge(graph, team, "RESPONSIBLE_FOR", role, source, section)


def _add_procurement(graph: Any) -> None:
    source = "procurement_approval_policy.md"
    section = "Approval Threshold Matrix"
    _node(graph, "Procurement Approval Policy", "Policy", policy_id="ABC-FIN-POL-007")
    _edge(graph, "Procurement Approval Policy", "DEFINED_IN", "Procurement Approval Policy", source, "Document Control")
    for name, minimum, maximum, approver in PROCUREMENT_THRESHOLDS:
        _node(graph, name, "ApprovalThreshold", min_amount_inr=minimum, max_amount_inr=maximum)
        _node(graph, approver, "Role")
        _edge(graph, name, "REQUIRES_APPROVAL_FROM", approver, source, section)
        _edge(graph, name, "DEFINED_IN", "Procurement Approval Policy", source, section)

    _node(graph, "Three-Quote Requirement", "Rule")
    _edge(graph, "Three-Quote Requirement", "APPLIES_TO", "Procurement Request Above ₹1,00,000", source, "Three-Quote Requirement")
    _edge(graph, "Three-Quote Requirement", "DEFINED_IN", "Procurement Approval Policy", source, "Three-Quote Requirement")


def _add_delay_escalation(graph: Any) -> None:
    source = "shipment_escalation_sop.md"
    _node(graph, "Shipment Delay Escalation SOP", "Procedure", policy_id="ABC-OPS-SOP-004")
    for level, minimum, maximum, owner, classification, communication in DELAY_LEVELS:
        _node(
            graph,
            level,
            "EscalationLevel",
            min_hours=minimum,
            max_hours=maximum,
            classification=classification,
            communication_requirement=communication,
        )
        _node(graph, owner, "Role")
        _edge(graph, level, "ESCALATES_TO", owner, source, "Delay Severity Classification")
        _edge(graph, level, "DEFINED_IN", "Shipment Delay Escalation SOP", source, "Delay Severity Classification")

    _node(graph, "Shipment Delay Over 24 Hours", "Rule", min_hours=24)
    _edge(graph, "Shipment Delay Over 24 Hours", "TRIGGERS", "Severity 3", source, "Escalation Timeline")
    _edge(graph, "Severity 3", "REQUIRES", "Escalation Ticket", source, "Escalation Timeline")
    _edge(graph, "Severity 3", "REQUIRES", "Customer Success Proactive Communication", source, "Escalation Timeline")

    _node(graph, "Shipment Delay Over 48 Hours", "Rule", min_hours=48)
    _edge(graph, "Shipment Delay Over 48 Hours", "TRIGGERS", "Severity 4", source, "Escalation Timeline")
    _edge(graph, "Severity 4", "REQUIRES", "Formal Written Customer Update", source, "Escalation Timeline")
    _edge(graph, "Severity 4", "RELATED_TO", "Service Credit Review", source, "Remediation and Service Credit Rules")

    for name, approver, max_amount in [
        ("Service Credit ₹1 to ₹25,000", "Finance Manager", 25000),
        ("Service Credit Above ₹25,000", "COO", None),
    ]:
        _node(graph, name, "ApprovalThreshold", max_amount_inr=max_amount)
        _edge(graph, name, "REQUIRES_APPROVAL_FROM", approver, source, "Remediation and Service Credit Rules")


def _add_customer_communication(graph: Any) -> None:
    source = "customer_communication_playbook.md"
    _node(graph, "Customer Communication Playbook", "Policy", policy_id="ABC-CS-PLY-002")
    _edge(graph, "Customer Communication Playbook", "RELATED_TO", "Shipment Delay Escalation SOP", source, "Shipment Delay Communication Rules")
    _edge(graph, "Customer Success Manager", "RESPONSIBLE_FOR", "Delay Over 24 Hours Proactive Update", source, "Shipment Delay Communication Rules")
    _edge(graph, "Finance Team", "APPROVES", "Service Credit", source, "Refund and Credit Communication Rules")
    _edge(graph, "COO", "APPROVES", "Credits Above ₹25,000", source, "Refund and Credit Communication Rules")


def _add_kpis(graph: Any) -> None:
    source = "inventory_kpi_guide.md"
    _node(graph, "Inventory KPI Guide", "Document", source_file=source, policy_id="ABC-INV-GDE-003")
    for kpi, metadata in KPI_MAPPINGS.items():
        _node(graph, kpi, "KPI", formula=metadata["formula"], columns=metadata["columns"])
        _edge(graph, kpi, "DEFINED_IN", "Inventory KPI Guide", source, metadata["section"])
        _edge(graph, kpi, "RESPONSIBLE_FOR", metadata["owner"], source, "KPI Summary Table")
        for column in metadata["columns"]:
            _node(graph, column, "Rule")
            _edge(graph, kpi, "CALCULATED_FROM", column, source, metadata["section"])
