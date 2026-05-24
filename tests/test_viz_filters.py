from knowledge_graph.load_graph_nx import load_graph_nx
from knowledge_graph.viz_filters import (
    branch_view,
    build_view,
    inventory_summary,
    policy_overview,
    sku_view,
)


def test_policy_overview_excludes_inventory_nodes():
    graph = load_graph_nx()
    view = policy_overview(graph)
    node_types = {attrs.get("type") for _, attrs in view.nodes(data=True)}
    assert "SKU" not in node_types
    assert "Category" not in node_types
    assert "Supplier" not in node_types
    assert view.number_of_nodes() > 0


def test_inventory_summary_node_count():
    graph = load_graph_nx()
    view = inventory_summary(graph)
    assert view.number_of_nodes() == 19
    node_types = {attrs.get("type") for _, attrs in view.nodes(data=True)}
    assert node_types == {"Branch", "Category", "Supplier"}
    assert view.number_of_edges() > 0


def test_sku_view_is_small_ego_network():
    graph = load_graph_nx()
    view = sku_view(graph, "PNTR-GRNTEA-03", radius=1)
    assert view.number_of_nodes() <= 10
    assert "PNTR-GRNTEA-03" in view


def test_branch_view_includes_mumbai_skus():
    graph = load_graph_nx()
    view = branch_view(graph, "Mumbai")
    assert "Mumbai" in view
    sku_nodes = [node for node, attrs in view.nodes(data=True) if attrs.get("type") == "SKU"]
    assert sku_nodes


def test_build_view_procurement_and_escalation_are_non_empty():
    graph = load_graph_nx()
    for view_name in ("procurement", "escalation", "kpi"):
        view = build_view(graph, view_name)
        assert view.number_of_nodes() > 0
        assert view.number_of_edges() > 0
