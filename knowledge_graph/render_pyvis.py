from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import networkx as nx
from pyvis.network import Network

NODE_COLORS = {
    "Role": "#2563eb",
    "Team": "#1d4ed8",
    "Branch": "#059669",
    "SKU": "#10b981",
    "Category": "#047857",
    "Supplier": "#0f766e",
    "Document": "#7c3aed",
    "Policy": "#9333ea",
    "Procedure": "#a855f7",
    "KPI": "#c026d3",
    "ApprovalThreshold": "#db2777",
    "EscalationLevel": "#e11d48",
    "Rule": "#f97316",
}

HIERARCHICAL_VIEWS = {"policy_overview", "procurement", "escalation", "kpi"}


def _short_label(node_id: str, limit: int = 24) -> str:
    if len(node_id) <= limit:
        return node_id
    return node_id[: limit - 3] + "..."


def _node_title(node_id: str, attrs: Dict[str, Any]) -> str:
    lines = [f"<b>{node_id}</b>", f"type: {attrs.get('type', 'unknown')}"]
    for key in (
        "branch",
        "category",
        "preferred_supplier",
        "stock_units",
        "aging_days",
        "formula",
        "classification",
        "communication_requirement",
        "source_file",
        "policy_id",
    ):
        if key in attrs and attrs[key] not in (None, ""):
            lines.append(f"{key}: {attrs[key]}")
    return "<br>".join(lines)


def _edge_title(attrs: Dict[str, Any], duplicate_count: int) -> str:
    lines = [
        f"relationship: {attrs.get('relationship', '')}",
        f"source_doc: {attrs.get('source_doc', '')}",
        f"section: {attrs.get('section', '')}",
    ]
    if "weight" in attrs:
        lines.append(f"weight: {attrs['weight']}")
    if "tooltip" in attrs:
        lines.append(str(attrs["tooltip"]))
    if duplicate_count > 1:
        lines.append(f"parallel_edges: {duplicate_count}")
    return "<br>".join(lines)


def _dedupe_edges(graph: nx.MultiDiGraph) -> Iterable[Tuple[str, str, Dict[str, Any], int]]:
    seen: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    counts: Dict[Tuple[str, str, str], int] = {}

    for source, target, attrs in graph.edges(data=True):
        relationship = str(attrs.get("relationship", "RELATED_TO"))
        key = (source, target, relationship)
        counts[key] = counts.get(key, 0) + 1
        if key not in seen:
            seen[key] = dict(attrs)

    for (source, target, relationship), attrs in seen.items():
        yield source, target, attrs, counts[(source, target, relationship)]


def _physics_options(view: str, physics: bool) -> str:
    if not physics:
        return """
        {
          "physics": { "enabled": false }
        }
        """

    if view in HIERARCHICAL_VIEWS:
        return """
        {
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "LR",
              "sortMethod": "directed"
            }
          },
          "physics": {
            "enabled": false
          }
        }
        """

    return """
    {
      "physics": {
        "enabled": true,
        "forceAtlas2Based": {
          "gravitationalConstant": -40,
          "centralGravity": 0.01,
          "springLength": 120,
          "avoidOverlap": 1
        },
        "solver": "forceAtlas2Based",
        "stabilization": {
          "iterations": 150
        }
      }
    }
    """


def render_pyvis_html(
    graph: nx.MultiDiGraph,
    output_path: Path,
    *,
    view: str,
    physics: bool = True,
) -> Path:
    net = Network(height="800px", width="100%", directed=True, notebook=False)
    net.barnes_hut_gravity = -8000

    for node_id, attrs in graph.nodes(data=True):
        node_type = str(attrs.get("type", "unknown"))
        net.add_node(
            node_id,
            label=_short_label(node_id),
            title=_node_title(node_id, attrs),
            color=NODE_COLORS.get(node_type, "#64748b"),
        )

    for source, target, attrs, duplicate_count in _dedupe_edges(graph):
        label = str(attrs.get("relationship", ""))
        if duplicate_count > 1:
            label = f"{label} x{duplicate_count}"
        net.add_edge(
            source,
            target,
            label=label,
            title=_edge_title(attrs, duplicate_count),
            arrows="to",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.set_options(_physics_options(view, physics))
    net.write_html(str(output_path), notebook=False)
    return output_path
