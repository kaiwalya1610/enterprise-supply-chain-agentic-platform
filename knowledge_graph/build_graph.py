from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import networkx as nx

from src.config import GRAPH_PATH
from knowledge_graph.kg_from_csv import add_csv_graph
from knowledge_graph.kg_from_docs import add_document_graph


def _export(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    nodes = [{"id": node_id, **attrs} for node_id, attrs in graph.nodes(data=True)]
    edges = [
        {"source": source, "target": target, **attrs}
        for source, target, _key, attrs in graph.edges(keys=True, data=True)
    ]
    nodes.sort(key=lambda item: item["id"])
    edges.sort(key=lambda item: (item["source"], item.get("relationship", ""), item["target"]))
    return {
        "schema_version": "1.0",
        "graph_type": "networkx-compatible-multidigraph",
        "nodes": nodes,
        "edges": edges,
    }


def build_graph() -> Dict[str, Any]:
    graph = nx.MultiDiGraph()
    add_document_graph(graph)
    add_csv_graph(graph)
    return _export(graph)


def write_graph(path: Path = GRAPH_PATH) -> Dict[str, Any]:
    graph_data = build_graph()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return graph_data


if __name__ == "__main__":
    data = write_graph()
    print(f"Wrote {GRAPH_PATH} with {len(data['nodes'])} nodes and {len(data['edges'])} edges")
