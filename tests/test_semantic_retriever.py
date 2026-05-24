from src.models import GraphFact, SourceChunk
from src.openrouter_client import RerankResult
from src import retriever as retriever_module
from src.retriever import DocumentRetriever, retrieve_parallel_context


class FakeOpenRouterClient:
    embedding_model = "google/gemini-embedding-2-preview"

    def __init__(self):
        self.rerank_calls = []

    def rerank(self, query, documents, top_n):
        self.rerank_calls.append((query, documents, top_n))
        return [
            RerankResult(index=1, relevance_score=0.95, text=documents[1]),
            RerankResult(index=0, relevance_score=0.4, text=documents[0]),
        ]


def test_openrouter_rerank_order_maps_back_to_chunks():
    chunks = [
        SourceChunk(
            id="a",
            text="first",
            source_file="a.md",
            section_heading="A",
            section_path="A",
            start_line=1,
            end_line=2,
            document_id="a",
            score=0.6,
            similarity_score=0.6,
        ),
        SourceChunk(
            id="b",
            text="second",
            source_file="b.md",
            section_heading="B",
            section_path="B",
            start_line=3,
            end_line=4,
            document_id="b",
            score=0.5,
            similarity_score=0.5,
        ),
    ]
    retriever = DocumentRetriever.__new__(DocumentRetriever)
    retriever.openrouter_client = FakeOpenRouterClient()
    retriever.warning = None

    reranked = retriever._rerank_openrouter("query", chunks, top_k=2)

    assert [chunk.id for chunk in reranked] == ["b", "a"]
    assert [chunk.score for chunk in reranked] == [0.95, 0.4]
    assert [chunk.similarity_score for chunk in reranked] == [0.5, 0.6]


def test_missing_openrouter_key_uses_lexical_fallback(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    retriever = DocumentRetriever(use_openrouter=True)
    results = retriever.search("shipment delay escalation", top_k=3)

    assert retriever.semantic_available is False
    assert "Semantic retrieval unavailable" in retriever.warning
    assert results


def test_parallel_context_merges_eligible_source_families(monkeypatch):
    submitted = []

    class ImmediateFuture:
        def __init__(self, value):
            self.value = value

        def result(self):
            return self.value

    class RecordingExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def submit(self, fn):
            submitted.append(fn.__name__)
            return ImmediateFuture(fn())

    class FakeDocumentRetriever:
        warning = None
        chunks = []

        def search(self, query, top_k, include_security_artifacts=False):
            return [
                SourceChunk(
                    id="doc-1",
                    text="Reorder level is calculated from stock and demand signals.",
                    source_file="inventory_kpi_guide.md",
                    section_heading="Reorder Level",
                    section_path="Inventory KPI Guide > Reorder Level",
                    start_line=10,
                    end_line=15,
                    document_id="inventory-kpi-guide",
                )
            ]

        def _search_lexical_fallback(self, query, top_k):
            return []

    def fake_graph_facts_for_question(question):
        return [
            GraphFact(
                subject="Reorder Level",
                relationship="USES_COLUMN",
                object="stock_units",
                source="inventory_kpi_guide.md",
            )
        ]

    monkeypatch.setattr(retriever_module, "ThreadPoolExecutor", RecordingExecutor)
    monkeypatch.setattr(retriever_module, "DocumentRetriever", FakeDocumentRetriever)
    monkeypatch.setattr("knowledge_graph.graph_queries.graph_facts_for_question", fake_graph_facts_for_question)

    bundle = retrieve_parallel_context("Which SKUs are below reorder level in the inventory snapshot CSV?")

    assert set(submitted) == {"fetch_graph", "fetch_docs", "fetch_structured"}
    assert bundle.route == "hybrid"
    assert bundle.graph_facts
    assert bundle.doc_chunks
    assert bundle.structured_result
    assert any(citation.source_file == "inventory_branch_snapshot.csv" for citation in bundle.citations)
