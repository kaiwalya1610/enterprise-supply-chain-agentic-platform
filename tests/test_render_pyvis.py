from pathlib import Path

from knowledge_graph.load_graph_nx import load_graph_nx
from knowledge_graph.render_pyvis import render_pyvis_html
from knowledge_graph.viz_filters import build_view


def test_render_procurement_view_writes_html(tmp_path: Path):
    graph = load_graph_nx()
    subgraph = build_view(graph, "procurement")
    output_path = tmp_path / "procurement.html"

    render_pyvis_html(subgraph, output_path, view="procurement")

    html = output_path.read_text(encoding="utf-8")
    assert output_path.exists()
    assert "nodes" in html
    assert "edges" in html
    assert "Procurement" in html or subgraph.number_of_nodes() == 0
