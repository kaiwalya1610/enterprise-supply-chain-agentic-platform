from src.models import SourceChunk
from src.openrouter_client import RerankResult
from src.retriever import DocumentRetriever


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
