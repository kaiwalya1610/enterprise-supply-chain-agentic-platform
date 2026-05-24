from src.structured_data import average_aging, top_aging_skus
from src.tools import analyze_inventory_snapshot, retrieve_supply_chain_context


def test_analyze_inventory_snapshot_wraps_pandas_functions():
    assert analyze_inventory_snapshot("average_aging") == average_aging()
    assert analyze_inventory_snapshot("top_aging_skus", limit=3)["rows"] == top_aging_skus(3)["rows"]


def test_retrieve_supply_chain_context_returns_full_context():
    context = retrieve_supply_chain_context("Explain the shipment delay escalation process.", top_k=2)

    assert context["route"] == "rag_policy"
    assert len(context["doc_chunks"]) <= 2
    assert context["citations"]
