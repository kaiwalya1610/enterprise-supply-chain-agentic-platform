import json
from pathlib import Path

import pytest

from knowledge_graph.graph_store import validate_graph_payload
from src.knowledge_ingestion import (
    classify_file,
    ingest_file,
    upsert_chunks_to_chroma,
    verify_chroma,
)
from src.ingest_docs import parse_markdown_file


class FakeEmbeddingClient:
    embedding_model = "fake-embedding-model"

    def embed_texts(self, texts, input_type):
        assert input_type == "search_document"
        return [[float(index + 1), 0.5] for index, _text in enumerate(texts)]


def test_classify_file_uses_heuristics_for_markdown_txt_csv_and_mode_override(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    markdown = tmp_path / "policy.md"
    markdown.write_text("# Policy\nThe CFO approves escalation thresholds.", encoding="utf-8")
    text = tmp_path / "notes.txt"
    text.write_text("General onboarding notes without durable entities.", encoding="utf-8")
    csv = tmp_path / "inventory.csv"
    csv.write_text("sku,branch,preferred_supplier\nSKU-1,Mumbai,Acme\n", encoding="utf-8")

    assert classify_file(markdown).storage_targets == ["embedding", "graph"]
    assert classify_file(text).storage_targets == ["embedding"]
    assert classify_file(csv).storage_targets == ["structured", "graph"]
    assert classify_file(markdown, mode="embedding").storage_targets == ["embedding"]
    assert classify_file(markdown, mode="hybrid").storage_targets == ["embedding", "graph"]


def test_dry_run_does_not_copy_manifest_chroma_or_graph(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    source = tmp_path / "new_policy.md"
    source.write_text("# New Policy\nThe Logistics Manager owns this process.", encoding="utf-8")
    manifest_path = tmp_path / "dataset" / "knowledge_manifest.json"
    chroma_dir = tmp_path / ".chroma" / "abc_ops_docs"
    graph_path = tmp_path / "knowledge_graph" / "graph.json"

    report = ingest_file(
        source,
        dry_run=True,
        chroma_dir=chroma_dir,
        manifest_path=manifest_path,
        graph_path=graph_path,
    )

    assert report.dry_run is True
    assert report.stored_path is None
    assert not manifest_path.exists()
    assert not chroma_dir.exists()
    assert not graph_path.exists()


def test_graph_payload_validation_rejects_missing_edge_source_doc():
    validate_graph_payload([{"id": "A", "type": "Role"}], [])
    with pytest.raises(ValueError, match="source_doc"):
        validate_graph_payload(
            [{"id": "A", "type": "Role"}, {"id": "B", "type": "Policy"}],
            [{"source": "A", "relationship": "RELATED_TO", "target": "B", "section": "Overview"}],
        )


def test_upsert_chunks_to_chroma_with_fake_embedding_client(tmp_path):
    source = tmp_path / "policy.md"
    source.write_text("# Policy\nThe CFO approves purchases.\n\n## Threshold\nAbove 500000 requires CFO.", encoding="utf-8")
    chunks = parse_markdown_file(source)
    chroma_dir = tmp_path / ".chroma" / "abc_ops_docs"

    result = upsert_chunks_to_chroma(chunks, FakeEmbeddingClient(), persist_dir=chroma_dir)
    verification = verify_chroma(chroma_dir)

    assert result["embedded_chunks"] == len(chunks)
    assert result["collection_name"] == "abc_ops_docs"
    assert verification["exists"] is True
    assert verification["collection_count"] == len(chunks)
    assert (chroma_dir / "index_manifest.json").exists()


def test_csv_ingestion_registers_schema_and_row_graph(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    source = tmp_path / "inventory.csv"
    source.write_text("sku,branch,preferred_supplier,category\nSKU-1,Mumbai,Acme,Pantry\n", encoding="utf-8")
    manifest_path = tmp_path / "dataset" / "knowledge_manifest.json"
    graph_path = tmp_path / "knowledge_graph" / "graph.json"

    report = ingest_file(
        source,
        copy_into_dataset=False,
        rebuild_chroma=False,
        manifest_path=manifest_path,
        graph_path=graph_path,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    assert report.structured_rows == 1
    assert report.structured_columns == ["sku", "branch", "preferred_supplier", "category"]
    assert manifest["files"][0]["structured_rows"] == 1
    assert any(edge["relationship"] == "SUPPLIED_BY" for edge in graph["edges"])
