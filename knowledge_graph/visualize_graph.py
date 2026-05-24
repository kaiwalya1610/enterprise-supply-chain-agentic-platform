from __future__ import annotations

import argparse
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph.load_graph_nx import graph_summary, load_graph_nx
from knowledge_graph.render_pyvis import render_pyvis_html
from knowledge_graph.viz_filters import VIEW_BUILDERS, build_view
from src.config import GRAPH_PATH, PROJECT_ROOT

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "knowledge_graph" / "viz"


def _default_output_path(view: str, sku: str | None, branch: str | None) -> Path:
    suffix = ""
    if sku:
        suffix = f"_{sku.replace('/', '-')}"
    elif branch:
        suffix = f"_{branch.replace('/', '-')}"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_OUTPUT_DIR / f"{view}{suffix}_{timestamp}.html"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render interactive HTML views of the abc.co knowledge graph.")
    parser.add_argument("--view", choices=sorted(VIEW_BUILDERS), help="Subgraph view to render.")
    parser.add_argument("--sku", help="SKU id for the sku view.")
    parser.add_argument("--branch", help="Branch name for the branch view.")
    parser.add_argument("--radius", type=int, default=1, help="Ego-network radius for the sku view.")
    parser.add_argument("--output", type=Path, help="Output HTML path.")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in a browser.")
    parser.add_argument("--no-physics", action="store_true", help="Disable physics/layout simulation.")
    parser.add_argument("--stats", action="store_true", help="Print graph summary JSON and exit.")
    parser.add_argument("--graph-path", type=Path, default=GRAPH_PATH, help="Path to graph.json.")
    args = parser.parse_args()

    graph = load_graph_nx(args.graph_path)

    if args.stats:
        print(json.dumps(graph_summary(graph), indent=2))
        return 0

    if not args.view:
        parser.error("--view is required unless --stats is set")

    subgraph = build_view(
        graph,
        args.view,
        sku=args.sku,
        branch=args.branch,
        radius=args.radius,
    )

    if args.view == "full" and subgraph.number_of_nodes() > 150:
        print(f"Warning: full view contains {subgraph.number_of_nodes()} nodes and may be hard to read.")

    output_path = args.output or _default_output_path(args.view, args.sku, args.branch)
    render_pyvis_html(
        subgraph,
        output_path,
        view=args.view,
        physics=not args.no_physics,
    )
    print(f"Wrote {output_path} with {subgraph.number_of_nodes()} nodes and {subgraph.number_of_edges()} edges")

    if args.open:
        webbrowser.open(output_path.resolve().as_uri())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
