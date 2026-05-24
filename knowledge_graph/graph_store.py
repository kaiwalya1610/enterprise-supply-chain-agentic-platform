from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from src.config import GRAPH_PATH


REQUIRED_EDGE_FIELDS = {"source", "relationship", "target", "source_doc", "section"}


def load_graph_data(path: Path = GRAPH_PATH) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        from knowledge_graph.build_graph import build_graph

        return build_graph()


def validate_graph_payload(nodes: Iterable[Dict[str, Any]], edges: Iterable[Dict[str, Any]]) -> None:
    for node in nodes:
        if not node.get("id") or not node.get("type"):
            raise ValueError(f"Graph node must include id and type: {node}")

    for edge in edges:
        missing = REQUIRED_EDGE_FIELDS - set(edge)
        if missing:
            raise ValueError(f"Graph edge missing required fields {sorted(missing)}: {edge}")
        if not edge["source"] or not edge["target"] or not edge["relationship"]:
            raise ValueError(f"Graph edge source, target, and relationship must be non-empty: {edge}")


def _node_key(node: Dict[str, Any]) -> str:
    return str(node["id"])


def _edge_key(edge: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return (
        str(edge["source"]),
        str(edge["relationship"]),
        str(edge["target"]),
        str(edge["source_doc"]),
        str(edge["section"]),
    )


def merge_nodes_edges(
    graph_data: Dict[str, Any],
    nodes: Iterable[Dict[str, Any]],
    edges: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    nodes = list(nodes)
    edges = list(edges)
    validate_graph_payload(nodes, edges)

    merged_nodes = {_node_key(node): dict(node) for node in graph_data.get("nodes", [])}
    for node in nodes:
        current = merged_nodes.get(_node_key(node), {})
        merged_nodes[_node_key(node)] = {**current, **node}

    merged_edges = {_edge_key(edge): dict(edge) for edge in graph_data.get("edges", [])}
    for edge in edges:
        merged_edges[_edge_key(edge)] = dict(edge)

    return {
        **graph_data,
        "schema_version": graph_data.get("schema_version", "1.0"),
        "graph_type": graph_data.get("graph_type", "networkx-compatible-multidigraph"),
        "nodes": sorted(merged_nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(
            merged_edges.values(),
            key=lambda item: (item["source"], item.get("relationship", ""), item["target"]),
        ),
    }


def write_graph_data(graph_data: Dict[str, Any], path: Path = GRAPH_PATH) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        from knowledge_graph.graph_queries import load_graph

        load_graph.cache_clear()
    except Exception:
        pass

    return graph_data
