from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from src.config import CHROMA_DIR, chroma_persistent_client
from src.guardrails import detect_guardrail_route
from src.ingest_docs import load_markdown_chunks
from src.models import Citation, RetrievalBundle, SourceChunk
from src.openrouter_client import OpenRouterClient, OpenRouterError
from src.question_router import missing_inputs_for_question, route_question
from src.structured_data import answer_structured_question


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "should",
    "the",
    "to",
    "what",
    "when",
    "which",
    "who",
    "with",
}

DOC_SOURCE_TERMS = {
    "approval",
    "approve",
    "approver",
    "communication",
    "credit",
    "customer",
    "delay",
    "escalation",
    "inventory",
    "kpi",
    "language",
    "policy",
    "procedure",
    "process",
    "procurement",
    "purchase",
    "refund",
    "reorder",
    "shipment",
    "slow-moving",
    "slow moving",
    "stockout",
    "supplier",
    "tone",
}

GRAPH_SOURCE_TERMS = {
    "approve",
    "approval",
    "approver",
    "category",
    "columns",
    "handles",
    "kpi",
    "notified",
    "related",
    "relationship",
    "responsible",
    "sku",
    "stocks",
    "stocked",
    "supplier",
    "who",
}

STRUCTURED_SOURCE_TERMS = {
    "average",
    "below reorder",
    "csv",
    "dataset",
    "dead-stock",
    "dead stock",
    "highest",
    "inventory snapshot",
    "lead time",
    "lead times",
    "lowest",
    "sales",
    "snapshot",
    "stockout risk",
    "slow-moving",
    "slow moving",
    "top",
    "total",
    "which branch",
    "which skus",
}


def _tokenize(text: str) -> List[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9₹,]+", text.lower()) if token not in STOPWORDS]


def eligible_sources_for_question(question: str) -> Set[str]:
    """Pick retrievers to try; this is not the final answer route."""
    normalized = question.lower()
    sources: Set[str] = set()
    if any(term in normalized for term in DOC_SOURCE_TERMS):
        sources.add("docs")
    if any(term in normalized for term in GRAPH_SOURCE_TERMS) or re.search(r"\b[A-Z]{3,5}-[A-Z0-9-]+\b", question):
        sources.add("graph")
    if any(term in normalized for term in STRUCTURED_SOURCE_TERMS) and any(
        inventory_term in normalized
        for inventory_term in ["inventory", "sku", "skus", "stock", "branch", "supplier", "sales", "csv", "snapshot"]
    ):
        sources.add("structured_csv")
    return sources


def _route_from_evidence(
    doc_chunks: List[SourceChunk],
    graph_facts: List[Any],
    structured_result: Optional[Dict[str, Any]],
) -> str:
    has_docs = bool(doc_chunks)
    has_graph = bool(graph_facts)
    has_structured = bool(structured_result)
    if has_structured and not (has_docs or has_graph):
        return "structured_data"
    if has_structured and (has_docs or has_graph):
        return "hybrid"
    if has_graph and has_docs:
        return "hybrid"
    if has_graph:
        return "graph_lookup"
    if has_docs:
        return "rag_policy"
    return "unsupported"


def _chunk_text_hash(chunks: List[SourceChunk]) -> str:
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda item: item.id):
        digest.update(chunk.id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(chunk.text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


class DocumentRetriever:
    def __init__(
        self,
        doc_paths: Optional[Iterable[Path]] = None,
        persist_dir: Path = CHROMA_DIR,
        use_openrouter: bool = True,
        candidate_k: int = 18,
        allow_fallback: bool = True,
        openrouter_client: Optional[OpenRouterClient] = None,
    ) -> None:
        self.chunks = load_markdown_chunks(doc_paths)
        self.persist_dir = persist_dir
        self.manifest_path = persist_dir / "index_manifest.json"
        self.candidate_k = candidate_k
        self.allow_fallback = allow_fallback
        self.collection = None
        self.semantic_available = False
        self.warning: Optional[str] = None
        self.openrouter_client: Optional[OpenRouterClient] = None

        if use_openrouter:
            self._try_init_semantic(openrouter_client)

    def _try_init_semantic(self, openrouter_client: Optional[OpenRouterClient]) -> None:
        try:
            self.openrouter_client = openrouter_client or OpenRouterClient()
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            chroma_client = chroma_persistent_client(self.persist_dir)
            self.collection = chroma_client.get_or_create_collection(
                name="abc_ops_docs",
                metadata={
                    "description": "OpenRouter-embedded section-aware abc.co operations policy chunks",
                    "embedding_model": self.openrouter_client.embedding_model,
                },
            )
            self._ensure_index()
            self.semantic_available = True
        except Exception as exc:
            self.collection = None
            self.semantic_available = False
            self.warning = f"Semantic retrieval unavailable; using lexical fallback. Reason: {exc}"
            if not self.allow_fallback:
                raise

    @staticmethod
    def _metadata(chunk: SourceChunk) -> Dict[str, object]:
        return {
            "source_file": chunk.source_file,
            "section_heading": chunk.section_heading,
            "section_path": chunk.section_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "document_id": chunk.document_id,
            "security_test_artifact": chunk.security_test_artifact,
        }

    def _manifest_base(self) -> Dict[str, Any]:
        return {
            "chunk_count": len(self.chunks),
            "content_hash": _chunk_text_hash(self.chunks),
            "embedding_model": self.openrouter_client.embedding_model,
        }

    def _read_manifest(self) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _manifest_matches(self, manifest: Optional[Dict[str, Any]]) -> bool:
        if not manifest:
            return False
        base = self._manifest_base()
        return (
            manifest.get("chunk_count") == base["chunk_count"]
            and manifest.get("content_hash") == base["content_hash"]
            and manifest.get("embedding_model") == base["embedding_model"]
            and manifest.get("embedding_dimension")
            and self.collection.count() == len(self.chunks)
        )

    def _ensure_index(self) -> None:
        manifest = self._read_manifest()
        if self._manifest_matches(manifest):
            return

        texts = [chunk.text for chunk in self.chunks]
        embeddings = self.openrouter_client.embed_texts(texts, input_type="search_document")
        if not embeddings:
            raise OpenRouterError("OpenRouter returned no document embeddings")
        dimension = len(embeddings[0])

        existing = self.collection.get(include=[])
        existing_ids = existing.get("ids") or []
        if existing_ids:
            self.collection.delete(ids=existing_ids)

        self.collection.add(
            ids=[chunk.id for chunk in self.chunks],
            documents=texts,
            metadatas=[self._metadata(chunk) for chunk in self.chunks],
            embeddings=embeddings,
        )

        manifest_data = {
            **self._manifest_base(),
            "embedding_dimension": dimension,
            "collection_name": "abc_ops_docs",
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    def search(self, query: str, top_k: int = 6, include_security_artifacts: bool = False) -> List[SourceChunk]:
        if self.semantic_available:
            try:
                chunks = self._search_semantic(query, candidate_k=max(self.candidate_k, top_k))
            except OpenRouterError as exc:
                self.warning = f"OpenRouter semantic query unavailable; using lexical fallback. Reason: {exc}"
                chunks = self._search_lexical_fallback(query, top_k=len(self.chunks))
            if not include_security_artifacts:
                chunks = [chunk for chunk in chunks if not chunk.security_test_artifact]
            return self._rerank_openrouter(query, chunks, top_k=top_k)

        chunks = self._search_lexical_fallback(query, top_k=len(self.chunks))
        if not include_security_artifacts:
            chunks = [chunk for chunk in chunks if not chunk.security_test_artifact]
        return chunks[:top_k]

    def _search_semantic(self, query: str, candidate_k: int) -> List[SourceChunk]:
        query_embedding = self.openrouter_client.embed_texts([query], input_type="search_query")[0]
        result = self.collection.query(query_embeddings=[query_embedding], n_results=candidate_k)
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        by_id = {chunk.id: chunk for chunk in self.chunks}
        chunks: List[SourceChunk] = []
        for chunk_id, distance in zip(ids, distances):
            if chunk_id not in by_id:
                continue
            similarity = 1.0 / (1.0 + float(distance))
            chunks.append(replace(by_id[chunk_id], score=similarity, similarity_score=similarity))
        return chunks

    def _rerank_openrouter(self, query: str, chunks: List[SourceChunk], top_k: int) -> List[SourceChunk]:
        if not chunks:
            return chunks[:top_k]
        try:
            documents = [chunk.text for chunk in chunks]
            results = self.openrouter_client.rerank(query, documents, top_n=top_k)
        except OpenRouterError as exc:
            self.warning = f"OpenRouter rerank unavailable; using Chroma similarity order. Reason: {exc}"
            return chunks[:top_k]
        reranked = [
            replace(chunks[result.index], score=result.relevance_score)
            for result in results
            if 0 <= result.index < len(chunks)
        ]
        return reranked[:top_k]

    def _search_lexical_fallback(self, query: str, top_k: int) -> List[SourceChunk]:
        query_counts = Counter(_tokenize(query))
        scored: List[SourceChunk] = []
        for chunk in self.chunks:
            text_tokens = _tokenize(f"{chunk.source_file} {chunk.section_path} {chunk.text}")
            text_counts = Counter(text_tokens)
            overlap = sum((query_counts & text_counts).values())
            score = overlap / math.sqrt(max(len(text_tokens), 1))
            if score > 0:
                scored.append(replace(chunk, score=self._fallback_boost(query, chunk, score)))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _fallback_boost(query: str, chunk: SourceChunk, score: float) -> float:
        query_lower = query.lower()
        section = chunk.section_path.lower()
        source = chunk.source_file

        if any(term in query_lower for term in ["shipment", "delay", "escalation"]):
            if source == "shipment_escalation_sop.md":
                score += 1.5
            for heading in ["delay severity classification", "escalation timeline", "standard procedure"]:
                if heading in section:
                    score += 1.5
            if "process" in query_lower and "escalation timeline" in section:
                score += 2.5
            if "records" in query_lower and "records and audit requirements" in section:
                score += 4.0
            if "service credit" in query_lower and "remediation and service credit rules" in section:
                score += 4.0
        if any(term in query_lower for term in ["procurement", "purchase", "approv", "three-quote", "quote"]):
            if source == "procurement_approval_policy.md":
                score += 1.5
            for heading in ["approval threshold matrix", "emergency procurement", "three-quote requirement"]:
                if heading in section:
                    score += 3.0
        if any(
            term in query_lower
            for term in ["inventory", "kpi", "aging", "slow-moving", "slow moving", "stockout", "reorder", "reorder point"]
        ):
            if source == "inventory_kpi_guide.md":
                score += 1.5
            for heading in [
                "inventory aging",
                "aging bands",
                "slow-moving inventory",
                "stockout risk",
                "reorder level",
                "kpi summary table",
            ]:
                if heading in section:
                    score += 3.0
            if "inventory aging" in query_lower and (
                "inventory aging > definition" in section or "inventory aging > calculation" in section
            ):
                score += 4.0
            if ("slow-moving" in query_lower or "slow moving" in query_lower) and "slow-moving inventory > definition" in section:
                score += 6.0
            if ("slow-moving" in query_lower or "slow moving" in query_lower) and "slow-moving inventory > exceptions" in section:
                score += 6.0
            if ("reorder" in query_lower or "reorder point" in query_lower) and "reorder level" in section:
                score += 6.0
        if any(term in query_lower for term in ["customer", "communication", "tone", "language", "refund", "credit"]):
            if source == "customer_communication_playbook.md":
                score += 1.5
            for heading in [
                "refund and credit communication rules",
                "tone guidelines",
                "words and phrases to avoid",
                "shipment delay communication rules",
            ]:
                if heading in section:
                    score += 3.0
            if "language" in query_lower and "words and phrases to avoid" in section:
                score += 4.0
        return score


def _dedupe_citations(chunks: List[SourceChunk]) -> List[Citation]:
    seen = set()
    citations: List[Citation] = []
    for chunk in chunks:
        key = (chunk.source_file, chunk.section_path, chunk.start_line, chunk.end_line)
        if key not in seen:
            seen.add(key)
            citations.append(chunk.citation())
    return citations


def retrieve_parallel_context(question: str, top_k: int = 6) -> RetrievalBundle:
    guardrail_route = detect_guardrail_route(question)
    if guardrail_route:
        return RetrievalBundle(question=question, route=guardrail_route.route, warnings=[guardrail_route.reason])

    if "prompt injection appendix" in question.lower():
        return RetrievalBundle(
            question=question,
            route="guardrail",
            warnings=["Question asks about a known security test artifact."],
        )

    missing = missing_inputs_for_question(question)
    if missing:
        return RetrievalBundle(
            question=question,
            route="ambiguous",
            warnings=["The question is missing inputs needed for a grounded answer."],
        )

    sources = eligible_sources_for_question(question)
    warnings: List[str] = []
    doc_chunks: List[SourceChunk] = []
    graph_facts = []
    structured_result = None
    retriever: Optional[DocumentRetriever] = None

    if not sources:
        return RetrievalBundle(
            question=question,
            route="unsupported",
            warnings=["No eligible source family matched the question."],
        )

    def fetch_graph() -> List[Any]:
        from knowledge_graph.graph_queries import graph_facts_for_question

        return graph_facts_for_question(question)

    def fetch_docs() -> tuple[List[SourceChunk], Optional[str], DocumentRetriever]:
        from knowledge_graph.graph_queries import expand_query_with_graph

        query = expand_query_with_graph(question) if "graph" in sources else question
        document_retriever = DocumentRetriever()
        chunks = document_retriever.search(query, top_k=top_k, include_security_artifacts=False)
        return chunks, document_retriever.warning, document_retriever

    def fetch_structured() -> Optional[Dict[str, Any]]:
        result = answer_structured_question(question)
        if result.get("operation") == "unsupported_structured_query":
            return None
        return result

    tasks = {}
    with ThreadPoolExecutor(max_workers=max(1, len(sources))) as executor:
        if "graph" in sources:
            tasks["graph"] = executor.submit(fetch_graph)
        if "docs" in sources:
            tasks["docs"] = executor.submit(fetch_docs)
        if "structured_csv" in sources:
            tasks["structured_csv"] = executor.submit(fetch_structured)

        for source, future in tasks.items():
            try:
                result = future.result()
            except Exception as exc:
                warnings.append(f"{source} retrieval unavailable. Reason: {exc}")
                continue
            if source == "graph":
                graph_facts = result
            elif source == "docs":
                doc_chunks, doc_warning, retriever = result
                if doc_warning:
                    warnings.append(doc_warning)
            elif source == "structured_csv":
                structured_result = result

    if retriever and graph_facts:
        graph_sources = {
            fact.source
            for fact in graph_facts
            if fact.source.endswith(".md") and fact.source not in {chunk.source_file for chunk in doc_chunks}
        }
        if graph_sources:
            from knowledge_graph.graph_queries import expand_query_with_graph

            support_chunks = retriever._search_lexical_fallback(expand_query_with_graph(question), top_k=len(retriever.chunks))
            for source in sorted(graph_sources):
                match = next((chunk for chunk in support_chunks if chunk.source_file == source), None)
                if match:
                    doc_chunks.append(match)

    citations = _dedupe_citations(doc_chunks)
    if structured_result:
        citations.append(
            Citation(
                source_file="inventory_branch_snapshot.csv",
                section_heading="CSV",
                section_path="inventory_branch_snapshot.csv",
                start_line=1,
                end_line=61,
            )
        )

    route = _route_from_evidence(doc_chunks, graph_facts, structured_result)
    if route == "unsupported" and not warnings:
        warnings.append("Retrieved evidence was empty after source eligibility and reranking.")

    return RetrievalBundle(
        question=question,
        route=route,
        doc_chunks=doc_chunks,
        graph_facts=graph_facts,
        structured_result=structured_result,
        citations=citations,
        warnings=warnings,
    )


def retrieve_context(question: str) -> RetrievalBundle:
    decision = route_question(question)
    warnings: List[str] = []
    doc_chunks: List[SourceChunk] = []
    graph_facts = []
    structured_result = None

    if decision.route in {"ambiguous", "unsupported"}:
        return RetrievalBundle(question=question, route=decision.route, warnings=[decision.reason])

    if decision.route == "structured_data":
        structured_result = answer_structured_question(question)
        return RetrievalBundle(
            question=question,
            route=decision.route,
            structured_result=structured_result,
            citations=[
                Citation(
                    source_file="inventory_branch_snapshot.csv",
                    section_heading="CSV",
                    section_path="inventory_branch_snapshot.csv",
                    start_line=1,
                    end_line=61,
                )
            ],
        )

    from knowledge_graph.graph_queries import expand_query_with_graph, graph_facts_for_question

    include_security = decision.route == "guardrail"
    if decision.route in {"graph_lookup", "hybrid", "guardrail"}:
        graph_facts = graph_facts_for_question(question)

    expanded_query = expand_query_with_graph(question) if decision.route in {"graph_lookup", "hybrid"} else question
    if decision.route in {"rag_policy", "hybrid", "guardrail", "graph_lookup"}:
        retriever = DocumentRetriever()
        doc_chunks = retriever.search(expanded_query, top_k=6, include_security_artifacts=include_security)
        graph_sources = {
            fact.source for fact in graph_facts if fact.source.endswith(".md") and fact.source not in {chunk.source_file for chunk in doc_chunks}
        }
        if graph_sources:
            support_chunks = retriever._search_lexical_fallback(expanded_query, top_k=len(retriever.chunks))
            for source in sorted(graph_sources):
                match = next((chunk for chunk in support_chunks if chunk.source_file == source), None)
                if match:
                    doc_chunks.append(match)
        if retriever.warning:
            warnings.append(retriever.warning)
        if any(chunk.security_test_artifact for chunk in doc_chunks):
            warnings.append("Retrieved prompt injection appendix is a security test artifact, not operational policy.")

    return RetrievalBundle(
        question=question,
        route=decision.route,
        doc_chunks=doc_chunks,
        graph_facts=graph_facts,
        structured_result=structured_result,
        citations=_dedupe_citations(doc_chunks),
        warnings=warnings,
    )
