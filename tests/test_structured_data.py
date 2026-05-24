from src.structured_data import (
    average_aging,
    branch_sales_totals,
    skus_below_reorder,
    supplier_average_lead_times,
    top_aging_skus,
)


def test_branch_sales_total_top_branch():
    result = branch_sales_totals()
    assert result["top_branch"] == "Mumbai"
    assert set(result["totals"]) == {"Mumbai", "Bangalore", "Delhi", "Hyderabad"}


def test_average_aging_is_computed():
    result = average_aging()
    assert result["average_aging_days"] > 0
    assert isinstance(result["average_aging_days"], float)


def test_top_aging_skus_match_expected_order():
    rows = top_aging_skus()["rows"]
    assert [row["sku"] for row in rows[:5]] == [
        "PNTR-GRNTEA-03",
        "ELEC-USB-CA-07",
        "FAC-DUSTBIN-01",
        "OFF-WHTBRD-01",
        "ERG-STOOL-AD-01",
    ]
    assert [row["aging_days"] for row in rows[:5]] == [157, 151, 143, 133, 127]


def test_below_reorder_contains_expected_skus():
    rows = skus_below_reorder()["rows"]
    skus = {row["sku"] for row in rows}
    assert {"PNTR-COFFEE-02", "OFF-TONER-HP01", "ELEC-WEBCAM-03", "ELEC-WEBCAM-05"}.issubset(skus)


def test_supplier_lead_time_ranking_contains_expected_suppliers():
    result = supplier_average_lead_times()
    suppliers = result["averages"]
    assert "WorkFlex Interiors" in suppliers
    assert "TechLink Wholesale" in suppliers
