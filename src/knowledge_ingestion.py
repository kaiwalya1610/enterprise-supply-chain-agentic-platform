from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

import pandas as pd

from knowledge_graph.graph_store import load_graph_data, merge_nodes_edges, write_graph_data
from src.config import (
    CHROMA_DIR,
    chroma_persistent_client,
    GRAPH_PATH,
    KNOWLEDGE_DOCS_DIR,
    KNOWLEDGE_MANIFEST_PATH,
    STRUCTURED_DATA_DIR,
)
from src.ingest_docs import parse_markdown_file
from src.models import SourceChunk
from src.openrouter_client import OpenRouterClient, OpenRouterError


IngestionMode = Literal["auto", "embedding", "structured", "graph", "hybrid"]

TEXT_SUFFIXES = {".md", ".txt"}
CSV_SUFFIXES = {".csv"}
GRAPH_KEYWORDS = {
    "approval",
    "approver",
    "threshold",
    "escalation",
    "responsible",
    "owner",
    "policy",
    "procedure",
    "supplier",
    "branch",
    "sku",
    "category",
    "kpi",
    "role",
    "team",
}
KNOWN_RELATIONSHIP_COLUMNS = {
    "sku",
    "branch",
    "preferred_supplier",
    "supplier",
    "category",
    "role",
    "team",
    "policy",
}


@dataclass
class ClassificationResult:
    storage_targets: List[str]
    reason: str
    document_type: str
    candidate_entities: List[str] = field(default_factory=list)
    candidate_relationships: List[str] = field(default_factory=list)
    used_llm: bool = False


@dataclass
class IngestionReport:
    source_path: str
    stored_path: Optional[str]
    content_hash: str
    mode: str
    dry_run: bool
    classification: Dict[str, Any]
    copied: bool = False
    embedded_chunks: int = 0
    chroma_collection: Optional[str] = None
    structured_rows: Optional[int] = None
    structured_columns: List[str] = field(default_factory=list)
    graph_nodes_added: int = 0
    graph_edges_added: int = 0
    warnings: List[str] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_destination(directory: Path, source: Path) -> Path:
    stem = source.stem.replace(" ", "_")
    suffix = source.suffix.lower()
    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists() and candidate.resolve() != source.resolve():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def _read_manifest(path: Path = KNOWLEDGE_MANIFEST_PATH) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"schema_version": "1.0", "files": []}


def _write_manifest(manifest: Dict[str, Any], path: Path = KNOWLEDGE_MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _upsert_manifest_entry(report: IngestionReport, manifest_path: Path = KNOWLEDGE_MANIFEST_PATH) -> None:
    manifest = _read_manifest(manifest_path)
    files = [item for item in manifest.get("files", []) if item.get("stored_path") != report.stored_path]
    files.append(
        {
            "source_path": report.source_path,
            "stored_path": report.stored_path,
            "content_hash": report.content_hash,
            "mode": report.mode,
            "classification": report.classification,
            "embedded_chunks": report.embedded_chunks,
            "chroma_collection": report.chroma_collection,
            "structured_rows": report.structured_rows,
            "structured_columns": report.structured_columns,
            "graph_nodes_added": report.graph_nodes_added,
            "graph_edges_added": report.graph_edges_added,
            "updated_at": _utc_now(),
        }
    )
    manifest["files"] = sorted(files, key=lambda item: item.get("stored_path") or item.get("source_path"))
    _write_manifest(manifest, manifest_path)


def _targets_for_mode(mode: IngestionMode, suffix: str) -> List[str]:
    if mode == "embedding":
        return ["embedding"]
    if mode == "structured":
        return ["structured"]
    if mode == "graph":
        return ["graph"]
    if mode == "hybrid":
        return ["embedding", "graph"]
    if suffix in CSV_SUFFIXES:
        return ["structured"]
    return ["embedding"]


def _heuristic_classification(path: Path, mode: IngestionMode = "auto") -> ClassificationResult:
    suffix = path.suffix.lower()
    if mode != "auto":
        targets = _targets_for_mode(mode, suffix)
        return ClassificationResult(
            storage_targets=targets,
            reason=f"Explicit mode '{mode}' was requested.",
            document_type="csv" if suffix in CSV_SUFFIXES else "text",
        )

    if suffix in CSV_SUFFIXES:
        df = pd.read_csv(path, nrows=25)
        columns = [str(column) for column in df.columns]
        normalized_columns = {column.lower() for column in columns}
        has_relationships = bool(normalized_columns & KNOWN_RELATIONSHIP_COLUMNS)
        return ClassificationResult(
            storage_targets=["structured", "graph"] if has_relationships else ["structured"],
            reason="CSV file detected; graph enabled when known entity columns are present.",
            document_type="csv",
            candidate_entities=columns,
            candidate_relationships=sorted(normalized_columns & KNOWN_RELATIONSHIP_COLUMNS),
        )

    text = path.read_text(encoding="utf-8", errors="replace")[:8000].lower()
    matched = sorted(keyword for keyword in GRAPH_KEYWORDS if keyword in text)
    targets = ["embedding", "graph"] if matched else ["embedding"]
    return ClassificationResult(
        storage_targets=targets,
        reason="Text file classified by deterministic policy/entity keywords.",
        document_type="text",
        candidate_entities=matched,
        candidate_relationships=matched,
    )


def _llm_classification(path: Path, client: OpenRouterClient) -> ClassificationResult:
    suffix = path.suffix.lower()
    sample = path.read_text(encoding="utf-8", errors="replace")[:12000]
    system = (
        "Classify enterprise knowledge files for a RAG system. Return only JSON with keys: "
        "storage_targets, reason, document_type, candidate_entities, candidate_relationships. "
        "storage_targets may contain embedding, structured, and graph."
    )
    user = f"File name: {path.name}\nSuffix: {suffix}\nContent sample:\n{sample}"
    data = client.chat_json(system, user)
    targets = [target for target in data.get("storage_targets", []) if target in {"embedding", "structured", "graph"}]
    if not targets:
        targets = _heuristic_classification(path).storage_targets
    return ClassificationResult(
        storage_targets=targets,
        reason=str(data.get("reason", "LLM classification")),
        document_type=str(data.get("document_type", "unknown")),
        candidate_entities=[str(item) for item in data.get("candidate_entities", [])],
        candidate_relationships=[str(item) for item in data.get("candidate_relationships", [])],
        used_llm=True,
    )


def classify_file(
    path: Path | str,
    mode: IngestionMode = "auto",
    openrouter_client: Optional[OpenRouterClient] = None,
) -> ClassificationResult:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in TEXT_SUFFIXES | CSV_SUFFIXES:
        raise ValueError(f"Unsupported knowledge file type: {suffix}")
    if mode != "auto":
        return _heuristic_classification(path, mode)
    if openrouter_client is not None:
        try:
            return _llm_classification(path, openrouter_client)
        except OpenRouterError:
            return _heuristic_classification(path, mode)
    if os.getenv("OPENROUTER_API_KEY"):
        try:
            return _llm_classification(path, OpenRouterClient())
        except OpenRouterError:
            return _heuristic_classification(path, mode)
    return _heuristic_classification(path, mode)


def _chunk_hash(chunk: SourceChunk) -> str:
    return hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()


def upsert_chunks_to_chroma(
    chunks: List[SourceChunk],
    openrouter_client: OpenRouterClient,
    persist_dir: Path = CHROMA_DIR,
) -> Dict[str, Any]:
    if not chunks:
        return {"collection_name": "abc_ops_docs", "embedded_chunks": 0, "sample_metadata": []}

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chroma_persistent_client(persist_dir)
    collection = client.get_or_create_collection(
        name="abc_ops_docs",
        metadata={
            "description": "OpenRouter-embedded dynamic abc.co knowledge chunks",
            "embedding_model": openrouter_client.embedding_model,
        },
    )
    embeddings = openrouter_client.embed_texts([chunk.text for chunk in chunks], input_type="search_document")
    metadatas = [
        {
            "source_file": chunk.source_file,
            "section_heading": chunk.section_heading,
            "section_path": chunk.section_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "document_id": chunk.document_id,
            "security_test_artifact": chunk.security_test_artifact,
            "content_hash": _chunk_hash(chunk),
            "ingested_at": _utc_now(),
        }
        for chunk in chunks
    ]
    collection.upsert(
        ids=[chunk.id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        metadatas=metadatas,
        embeddings=embeddings,
    )

    manifest_path = persist_dir / "index_manifest.json"
    manifest = {
        "collection_name": collection.name,
        "chunk_count": collection.count(),
        "embedding_model": openrouter_client.embedding_model,
        "embedding_dimension": len(embeddings[0]),
        "dynamic_file_hashes": {
            metadata["source_file"]: metadata["content_hash"]
            for metadata in metadatas
        },
        "updated_at": _utc_now(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "collection_name": collection.name,
        "embedded_chunks": len(chunks),
        "sample_metadata": metadatas[:3],
    }


def verify_chroma(persist_dir: Path = CHROMA_DIR) -> Dict[str, Any]:
    if not persist_dir.exists():
        return {"exists": False, "collection_count": 0, "sample_metadata": []}
    client = chroma_persistent_client(persist_dir)
    collection = client.get_collection("abc_ops_docs")
    sample = collection.peek(limit=3)
    return {
        "exists": True,
        "collection_name": collection.name,
        "collection_count": collection.count(),
        "sample_metadata": sample.get("metadatas", []),
    }


def _csv_graph_payload(path: Path) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    df = pd.read_csv(path)
    columns = {column.lower(): column for column in df.columns}
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    def value(row: Dict[str, Any], *names: str) -> Optional[str]:
        for name in names:
            column = columns.get(name)
            if column and pd.notna(row.get(column)):
                return str(row[column])
        return None

    for row in df.to_dict(orient="records"):
        sku = value(row, "sku")
        branch = value(row, "branch")
        supplier = value(row, "preferred_supplier", "supplier")
        category = value(row, "category")
        role = value(row, "role")
        team = value(row, "team")
        policy = value(row, "policy")

        for node_id, node_type in [
            (sku, "SKU"),
            (branch, "Branch"),
            (supplier, "Supplier"),
            (category, "Category"),
            (role, "Role"),
            (team, "Team"),
            (policy, "Policy"),
        ]:
            if node_id:
                nodes.append({"id": node_id, "type": node_type, "name": node_id, "source_file": path.name})

        for target, relationship in [(branch, "STOCKED_AT"), (supplier, "SUPPLIED_BY"), (category, "BELONGS_TO_CATEGORY")]:
            if sku and target:
                edges.append(
                    {
                        "source": sku,
                        "relationship": relationship,
                        "target": target,
                        "source_doc": path.name,
                        "section": "CSV row",
                    }
                )
        if team and role:
            edges.append(
                {
                    "source": team,
                    "relationship": "RESPONSIBLE_FOR",
                    "target": role,
                    "source_doc": path.name,
                    "section": "CSV row",
                }
            )
        if policy and role:
            edges.append(
                {
                    "source": policy,
                    "relationship": "REQUIRES_APPROVAL_FROM",
                    "target": role,
                    "source_doc": path.name,
                    "section": "CSV row",
                }
            )

    unique_nodes = {node["id"]: node for node in nodes}
    unique_edges = {
        (edge["source"], edge["relationship"], edge["target"], edge["source_doc"], edge["section"]): edge
        for edge in edges
    }
    return list(unique_nodes.values()), list(unique_edges.values())


def _llm_graph_payload(path: Path, client: OpenRouterClient) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    sample = path.read_text(encoding="utf-8", errors="replace")[:15000]
    system = (
        "Extract durable enterprise knowledge graph facts as JSON. Return an object with arrays nodes and edges. "
        "Nodes require id, type, and optional properties. Edges require source, relationship, target, source_doc, section. "
        "Use only relationships from this style: OWNS, APPROVES, ESCALATES_TO, RESPONSIBLE_FOR, DEFINED_IN, "
        "APPLIES_TO, STOCKED_AT, SUPPLIED_BY, BELONGS_TO_CATEGORY, TRIGGERS, REQUIRES_APPROVAL_FROM, "
        "CALCULATED_FROM, RELATED_TO, HAS_SKU, REQUIRES."
    )
    user = f"Source document: {path.name}\nContent sample:\n{sample}"
    data = client.chat_json(system, user)
    nodes = []
    for node in data.get("nodes", []):
        if "properties" in node and isinstance(node["properties"], dict):
            node = {key: value for key, value in node.items() if key != "properties"} | node["properties"]
        nodes.append(node)
    return nodes, list(data.get("edges", []))


def _merge_graph_payload(
    path: Path,
    classification: ClassificationResult,
    openrouter_client: Optional[OpenRouterClient],
    graph_path: Path,
) -> tuple[int, int, List[str]]:
    warnings: List[str] = []
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    if path.suffix.lower() in CSV_SUFFIXES:
        nodes, edges = _csv_graph_payload(path)
    elif classification.used_llm and openrouter_client is not None:
        try:
            nodes, edges = _llm_graph_payload(path, openrouter_client)
        except OpenRouterError as exc:
            warnings.append(f"LLM graph extraction skipped: {exc}")
    else:
        warnings.append("Graph target selected, but no LLM client is available for text graph extraction.")

    if not nodes and not edges:
        return 0, 0, warnings

    before = load_graph_data(graph_path)
    merged = merge_nodes_edges(before, nodes, edges)
    write_graph_data(merged, graph_path)
    return (
        max(0, len(merged.get("nodes", [])) - len(before.get("nodes", []))),
        max(0, len(merged.get("edges", [])) - len(before.get("edges", []))),
        warnings,
    )


def _copy_source(path: Path, targets: Iterable[str], copy_into_dataset: bool) -> Path:
    if not copy_into_dataset:
        return path
    if "structured" in targets and path.suffix.lower() in CSV_SUFFIXES:
        directory = STRUCTURED_DATA_DIR
    else:
        directory = KNOWLEDGE_DOCS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    destination = _safe_destination(directory, path)
    if destination.resolve() != path.resolve():
        shutil.copy2(path, destination)
    return destination


def ingest_file(
    path: Path | str,
    mode: IngestionMode = "auto",
    copy_into_dataset: bool = True,
    rebuild_chroma: bool = True,
    update_graph: bool = True,
    dry_run: bool = False,
    openrouter_client: Optional[OpenRouterClient] = None,
    chroma_dir: Path = CHROMA_DIR,
    manifest_path: Path = KNOWLEDGE_MANIFEST_PATH,
    graph_path: Path = GRAPH_PATH,
) -> IngestionReport:
    source = Path(path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(source)

    active_openrouter_client = openrouter_client
    if active_openrouter_client is None and mode == "auto" and os.getenv("OPENROUTER_API_KEY"):
        try:
            active_openrouter_client = OpenRouterClient()
        except OpenRouterError:
            active_openrouter_client = None

    classification = classify_file(source, mode=mode, openrouter_client=active_openrouter_client)
    targets = classification.storage_targets
    content_hash = _content_hash(source)
    stored_path = source if dry_run else _copy_source(source, targets, copy_into_dataset)

    report = IngestionReport(
        source_path=str(source),
        stored_path=str(stored_path) if not dry_run else None,
        content_hash=content_hash,
        mode=mode,
        dry_run=dry_run,
        classification=asdict(classification),
        copied=copy_into_dataset and not dry_run and stored_path != source,
    )

    if dry_run:
        return report

    if "structured" in targets and stored_path.suffix.lower() in CSV_SUFFIXES:
        df = pd.read_csv(stored_path)
        report.structured_rows = len(df)
        report.structured_columns = [str(column) for column in df.columns]

    if "embedding" in targets and stored_path.suffix.lower() in TEXT_SUFFIXES and rebuild_chroma:
        try:
            client = active_openrouter_client or OpenRouterClient()
            chunks = parse_markdown_file(stored_path)
            chroma_result = upsert_chunks_to_chroma(chunks, client, persist_dir=chroma_dir)
            report.embedded_chunks = chroma_result["embedded_chunks"]
            report.chroma_collection = chroma_result["collection_name"]
        except Exception as exc:
            report.warnings.append(f"Chroma embedding skipped: {exc}")

    if "graph" in targets and update_graph:
        nodes_added, edges_added, warnings = _merge_graph_payload(
            stored_path,
            classification,
            active_openrouter_client,
            graph_path,
        )
        report.graph_nodes_added = nodes_added
        report.graph_edges_added = edges_added
        report.warnings.extend(warnings)

    _upsert_manifest_entry(report, manifest_path)
    return report


def report_to_json(report: IngestionReport) -> str:
    return json.dumps(asdict(report), indent=2, ensure_ascii=False)
