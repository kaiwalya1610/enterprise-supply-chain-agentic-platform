import json
import urllib.error
from unittest.mock import patch

from src.openrouter_client import OpenRouterClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_embedding_request_payload_uses_openrouter_endpoint_and_input_type():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = dict(request.header_items())
        return FakeResponse(
            {
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2]},
                    {"index": 1, "embedding": [0.3, 0.4]},
                ]
            }
        )

    client = OpenRouterClient(api_key="test-key", max_retries=0)
    with patch("urllib.request.urlopen", fake_urlopen):
        embeddings = client.embed_texts(["doc one", "doc two"], input_type="search_document")

    assert captured["url"].endswith("/embeddings")
    assert captured["payload"]["model"] == "google/gemini-embedding-2-preview"
    assert captured["payload"]["input"] == ["doc one", "doc two"]
    assert captured["payload"]["encoding_format"] == "float"
    assert captured["payload"]["input_type"] == "search_document"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_texts_batches_requests_when_input_exceeds_provider_limit():
    batch_sizes = []
    call_count = 0

    def fake_urlopen(request, timeout):
        nonlocal call_count
        call_count += 1
        payload = json.loads(request.data.decode("utf-8"))
        batch_sizes.append(len(payload["input"]))
        return FakeResponse(
            {
                "data": [
                    {"index": index, "embedding": [float(index)]}
                    for index in range(len(payload["input"]))
                ]
            }
        )

    client = OpenRouterClient(api_key="test-key", max_retries=0)
    texts = [f"doc-{index}" for index in range(134)]
    with patch("urllib.request.urlopen", fake_urlopen):
        embeddings = client.embed_texts(texts, input_type="search_document")

    assert call_count == 2
    assert batch_sizes == [100, 34]
    assert len(embeddings) == 134
    assert embeddings[0] == [0.0]
    assert embeddings[133] == [33.0]


def test_rerank_request_payload_maps_results():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "results": [
                    {"index": 1, "relevance_score": 0.9, "document": {"text": "second"}},
                    {"index": 0, "relevance_score": 0.3, "document": {"text": "first"}},
                ]
            }
        )

    client = OpenRouterClient(api_key="test-key", max_retries=0)
    with patch("urllib.request.urlopen", fake_urlopen):
        results = client.rerank("query", ["first", "second"], top_n=2)

    assert captured["url"].endswith("/rerank")
    assert captured["payload"]["model"] == "cohere/rerank-4-fast"
    assert captured["payload"]["query"] == "query"
    assert captured["payload"]["documents"] == ["first", "second"]
    assert captured["payload"]["top_n"] == 2
    assert [result.index for result in results] == [1, 0]
    assert [result.relevance_score for result in results] == [0.9, 0.3]
