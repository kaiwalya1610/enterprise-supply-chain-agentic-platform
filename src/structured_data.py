from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.config import CSV_PATH


def load_inventory(path: Path = CSV_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def _df(data: Optional[pd.DataFrame]) -> pd.DataFrame:
    return data if data is not None else load_inventory()


def _round(value: float) -> float:
    return round(float(value), 2)


def branch_sales_totals(data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    totals = _df(data).groupby("branch")["sales_last_30_days"].sum().sort_values(ascending=False)
    return {
        "operation": "branch_sales_totals",
        "top_branch": totals.index[0],
        "totals": {branch: int(value) for branch, value in totals.items()},
    }


def average_aging(data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    return {"operation": "average_aging", "average_aging_days": _round(_df(data)["aging_days"].mean())}


def top_aging_skus(limit: int = 5, data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    fields = ["sku", "product_name", "branch", "aging_days", "preferred_supplier"]
    rows = _df(data).sort_values("aging_days", ascending=False).head(limit)[fields].to_dict(orient="records")
    return {"operation": "top_aging_skus", "rows": rows}


def skus_below_reorder(data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    fields = ["sku", "product_name", "branch", "stock_units", "reorder_level", "preferred_supplier"]
    df = _df(data)
    rows = df[df["stock_units"] < df["reorder_level"]][fields].to_dict(orient="records")
    return {"operation": "skus_below_reorder", "rows": rows}


def branch_average_aging(data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    averages = _df(data).groupby("branch")["aging_days"].mean().sort_values(ascending=False)
    values = {branch: _round(value) for branch, value in averages.items()}
    return {"operation": "branch_average_aging", "top_branch": next(iter(values)), "averages": values}


def supplier_average_lead_times(limit: int = 5, data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    averages = (
        _df(data).groupby("preferred_supplier")["supplier_lead_time_days"].mean().sort_values(ascending=False).head(limit)
    )
    values = {supplier: _round(value) for supplier, value in averages.items()}
    return {"operation": "supplier_average_lead_times", "averages": values}


def slow_moving_inventory(data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    fields = ["sku", "product_name", "branch", "aging_days", "sales_last_30_days", "reserved_for_contract_customer"]
    df = _df(data)
    rows = df[(df["aging_days"] > 60) & (df["sales_last_30_days"] < 20)][fields].to_dict(orient="records")
    return {"operation": "slow_moving_inventory", "rows": rows}


def dead_stock_candidates(data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    fields = ["sku", "product_name", "branch", "aging_days", "sales_last_30_days", "reserved_for_contract_customer"]
    df = _df(data)
    rows = df[(df["aging_days"] > 120) & (df["sales_last_30_days"] == 0)][fields].to_dict(orient="records")
    return {"operation": "dead_stock_candidates", "rows": rows}


def stockout_risk_items(data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    fields = ["sku", "product_name", "branch", "stock_units", "reorder_level", "supplier_lead_time_days"]
    df = _df(data)
    rows = df[df["stock_units"] <= df["reorder_level"]][fields].to_dict(orient="records")
    return {"operation": "stockout_risk_items", "rows": rows}


def answer_structured_question(question: str) -> Dict[str, Any]:
    normalized = question.lower()
    if "highest total sales" in normalized or ("total sales" in normalized and "branch" in normalized):
        return branch_sales_totals()
    if "average inventory aging across all" in normalized or "average aging across all" in normalized:
        return average_aging()
    if "top 5" in normalized and ("aging" in normalized or "aging days" in normalized):
        return top_aging_skus(5)
    if "below" in normalized and "reorder" in normalized:
        return skus_below_reorder()
    if "highest average inventory aging" in normalized or ("average" in normalized and "aging" in normalized and "branch" in normalized):
        return branch_average_aging()
    if "supplier" in normalized and "lead time" in normalized:
        return supplier_average_lead_times()
    if "slow-moving" in normalized or "slow moving" in normalized:
        return slow_moving_inventory()
    if "dead-stock" in normalized or "dead stock" in normalized:
        return dead_stock_candidates()
    if "stockout risk" in normalized:
        return stockout_risk_items()
    return {"operation": "unsupported_structured_query", "message": "No deterministic CSV operation matched the question."}
