from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict

import networkx as nx

from knowledge_graph.graph_store import load_graph_data, validate_graph_payload
from src.config import GRAPH_PATH


def load_graph_nx(path: Path = GRAPH_PATH) -> nx.MultiDiGraph:
    data = load_graph_data(path)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    validate_graph_payload(nodes, edges)

    graph = nx.MultiDiGraph()
    for node in nodes:
        node_id = node["id"]
        attrs = {key: value for key, value in node.items() if key != "id"}
        graph.add_node(node_id, **attrs)

    for index, edge in enumerate(edges):
        graph.add_edge(
            edge["source"],
            edge["target"],
            key=f"{edge['relationship']}:{index}",
            **edge,
        )
    return graph


def graph_summary(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    node_types = Counter(attrs.get("type", "unknown") for _, attrs in graph.nodes(data=True))
    edge_types = Counter(attrs.get("relationship", "unknown") for _, _, attrs in graph.edges(data=True))
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "node_types": dict(sorted(node_types.items())),
        "edge_types": dict(sorted(edge_types.items())),
    }
