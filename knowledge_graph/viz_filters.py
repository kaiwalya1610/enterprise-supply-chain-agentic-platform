from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional, Set

import networkx as nx

POLICY_EXCLUDED_TYPES = {"SKU", "Category", "Supplier"}
PROCUREMENT_TYPES = {"ApprovalThreshold", "Policy", "Rule", "Role", "Document"}
ESCALATION_TYPES = {"EscalationLevel", "Procedure", "Rule", "Role", "Document", "Policy"}
KPI_TYPES = {"KPI", "Rule", "Document", "Team", "Role"}
INVENTORY_NODE_TYPES = {"Branch", "Category", "Supplier"}


def _node_type(graph: nx.MultiDiGraph, node: str) -> str:
    return str(graph.nodes[node].get("type", ""))


def _collect_neighbors(graph: nx.MultiDiGraph, seeds: Iterable[str], depth: int = 1) -> Set[str]:
    selected = set(seeds)
    frontier = set(seeds)
    for _ in range(depth):
        next_frontier: Set[str] = set()
        for node in frontier:
            next_frontier.update(graph.predecessors(node))
            next_frontier.update(graph.successors(node))
        selected.update(next_frontier)
        frontier = next_frontier
    return selected


def _subgraph(graph: nx.MultiDiGraph, nodes: Iterable[str]) -> nx.MultiDiGraph:
    return graph.subgraph(nodes).copy()


def policy_overview(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    nodes = [node for node, attrs in graph.nodes(data=True) if attrs.get("type") not in POLICY_EXCLUDED_TYPES]
    return _subgraph(graph, nodes)


def procurement(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    seeds = [
        node
        for node, attrs in graph.nodes(data=True)
        if attrs.get("type") in {"ApprovalThreshold", "Policy", "Rule"}
        or "Procurement" in node
        or "Service Credit" in node
        or "Three-Quote" in node
    ]
    nodes = _collect_neighbors(graph, seeds, depth=1)
    nodes = {node for node in nodes if _node_type(graph, node) in PROCUREMENT_TYPES or node in seeds}
    return _subgraph(graph, nodes)


def escalation(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    seeds = [
        node
        for node, attrs in graph.nodes(data=True)
        if attrs.get("type") in {"EscalationLevel", "Procedure", "Rule"}
        or node.startswith("Severity ")
        or "Shipment Delay" in node
        or "Customer Success" in node
    ]
    nodes = _collect_neighbors(graph, seeds, depth=1)
    nodes = {node for node in nodes if _node_type(graph, node) in ESCALATION_TYPES or node in seeds}
    return _subgraph(graph, nodes)


def kpi(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    seeds = [node for node, attrs in graph.nodes(data=True) if attrs.get("type") == "KPI"]
    nodes = _collect_neighbors(graph, seeds, depth=2)
    nodes = {node for node in nodes if _node_type(graph, node) in KPI_TYPES or node in seeds}
    return _subgraph(graph, nodes)


def inventory_summary(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    summary = nx.MultiDiGraph()
    for node, attrs in graph.nodes(data=True):
        if attrs.get("type") in INVENTORY_NODE_TYPES:
            summary.add_node(node, **attrs)

    branch_category = Counter()
    branch_supplier = Counter()
    category_supplier = Counter()

    for node, attrs in graph.nodes(data=True):
        if attrs.get("type") != "SKU":
            continue
        branch = attrs.get("branch")
        category = attrs.get("category")
        supplier = attrs.get("preferred_supplier")
        if branch and category:
            branch_category[(branch, category)] += 1
        if branch and supplier:
            branch_supplier[(branch, supplier)] += 1
        if category and supplier:
            category_supplier[(category, supplier)] += 1

    for (source, target), count in branch_category.items():
        summary.add_edge(
            source,
            target,
            key=f"branch_category:{source}:{target}",
            relationship="STOCKS_CATEGORY",
            weight=count,
            source_doc="inventory_branch_snapshot.csv",
            section="aggregated",
            tooltip=f"{count} SKUs",
        )
    for (source, target), count in branch_supplier.items():
        summary.add_edge(
            source,
            target,
            key=f"branch_supplier:{source}:{target}",
            relationship="STOCKED_BY_SUPPLIER",
            weight=count,
            source_doc="inventory_branch_snapshot.csv",
            section="aggregated",
            tooltip=f"{count} SKUs",
        )
    for (source, target), count in category_supplier.items():
        summary.add_edge(
            source,
            target,
            key=f"category_supplier:{source}:{target}",
            relationship="SUPPLIED_IN_CATEGORY",
            weight=count,
            source_doc="inventory_branch_snapshot.csv",
            section="aggregated",
            tooltip=f"{count} SKUs",
        )
    return summary


def branch_view(graph: nx.MultiDiGraph, branch: str) -> nx.MultiDiGraph:
    if branch not in graph:
        raise ValueError(f"Branch not found in graph: {branch}")

    nodes: Set[str] = {branch}
    for sku in graph.successors(branch):
        if _node_type(graph, sku) == "SKU":
            nodes.add(sku)
    for sku in graph.predecessors(branch):
        if _node_type(graph, sku) == "SKU":
            nodes.add(sku)

    expanded = set(nodes)
    for sku in list(nodes):
        if _node_type(graph, sku) != "SKU":
            continue
        expanded.update(graph.successors(sku))
        expanded.update(graph.predecessors(sku))

    pruned = {
        node
        for node in expanded
        if _node_type(graph, node) in {"Branch", "SKU", "Category", "Supplier"} or node == branch
    }
    return _subgraph(graph, pruned)


def sku_view(graph: nx.MultiDiGraph, sku: str, radius: int = 1) -> nx.MultiDiGraph:
    if sku not in graph:
        raise ValueError(f"SKU not found in graph: {sku}")
    undirected = graph.to_undirected(as_view=False)
    ego = nx.ego_graph(undirected, sku, radius=radius)
    return _subgraph(graph, ego.nodes)


def full_view(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    return graph.copy()


VIEW_BUILDERS = {
    "policy_overview": lambda graph, **_: policy_overview(graph),
    "procurement": lambda graph, **_: procurement(graph),
    "escalation": lambda graph, **_: escalation(graph),
    "kpi": lambda graph, **_: kpi(graph),
    "inventory_summary": lambda graph, **_: inventory_summary(graph),
    "branch": lambda graph, branch=None, **_: branch_view(graph, branch or ""),
    "sku": lambda graph, sku=None, radius=1, **_: sku_view(graph, sku or "", radius=radius),
    "full": lambda graph, **_: full_view(graph),
}


def build_view(
    graph: nx.MultiDiGraph,
    view: str,
    *,
    sku: Optional[str] = None,
    branch: Optional[str] = None,
    radius: int = 1,
) -> nx.MultiDiGraph:
    if view not in VIEW_BUILDERS:
        raise ValueError(f"Unknown view '{view}'. Expected one of: {', '.join(sorted(VIEW_BUILDERS))}")

    if view == "sku" and not sku:
        raise ValueError("View 'sku' requires --sku")
    if view == "branch" and not branch:
        raise ValueError("View 'branch' requires --branch")

    return VIEW_BUILDERS[view](graph, sku=sku, branch=branch, radius=radius)
