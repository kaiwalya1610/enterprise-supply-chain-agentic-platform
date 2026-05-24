from __future__ import annotations

from typing import Any

from src.structured_data import load_inventory


def add_csv_graph(graph: Any) -> None:
    source = "inventory_branch_snapshot.csv"

    for row in load_inventory().to_dict(orient="records"):
        sku = row["sku"]
        branch = row["branch"]
        category = row["category"]
        supplier = row["preferred_supplier"]

        graph.add_node(sku, type="SKU", **{key: row[key] for key in row})
        graph.add_node(branch, type="Branch", name=branch)
        graph.add_node(category, type="Category", name=category)
        graph.add_node(supplier, type="Supplier", name=supplier)

        graph.add_edge(sku, branch, relationship="STOCKED_AT", source_doc=source, section="CSV row")
        graph.add_edge(branch, sku, relationship="HAS_SKU", source_doc=source, section="CSV row")
        graph.add_edge(sku, category, relationship="BELONGS_TO_CATEGORY", source_doc=source, section="CSV row")
        graph.add_edge(category, sku, relationship="HAS_SKU", source_doc=source, section="CSV row")
        graph.add_edge(sku, supplier, relationship="SUPPLIED_BY", source_doc=source, section="CSV row")
