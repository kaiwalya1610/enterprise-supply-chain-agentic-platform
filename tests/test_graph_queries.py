from knowledge_graph.graph_queries import (
    find_delay_escalation,
    find_kpi_relationship,
    find_procurement_approver,
    find_sku_relationship,
)


def test_procurement_approval_threshold_boundaries():
    cases = [
        (25000, "Team Lead"),
        (25001, "Department Head"),
        (100000, "Department Head"),
        (100001, "Finance Manager"),
        (500000, "Finance Manager"),
        (500001, "CFO"),
        (1500000, "CFO"),
        (1500001, "COO and CFO"),
    ]
    for amount, approver in cases:
        assert find_procurement_approver(amount)["required_approver"] == approver


def test_delay_escalation_threshold_boundaries():
    cases = [
        (5, "Severity 0"),
        (6, "Severity 1"),
        (12, "Severity 2"),
        (24, "Severity 3"),
        (25, "Severity 3"),
        (48, "Severity 4"),
        (49, "Severity 4"),
        (72, "Severity 4"),
    ]
    for hours, severity in cases:
        assert find_delay_escalation(hours)["severity"] == severity


def test_kpi_relationship_synonym_target():
    result = find_kpi_relationship("Stockout Risk")
    assert result["found"] is True
    assert "stock_units" in result["columns"]
    assert "reorder_level" in result["columns"]


def test_known_and_unknown_sku_lookup():
    known = find_sku_relationship("PNTR-GRNTEA-03")
    assert known["found"] is True
    assert known["branch"] == "Hyderabad"
    assert known["supplier"]

    unknown = find_sku_relationship("NOPE-SKU-000")
    assert unknown["found"] is False
