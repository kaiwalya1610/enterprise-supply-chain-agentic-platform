from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from src.config import (
    OPENROUTER_APP_TITLE,
    OPENROUTER_BASE_URL,
    OPENROUTER_CHAT_MODEL,
    OPENROUTER_EMBEDDING_MODEL,
    OPENROUTER_RERANK_MODEL,
)
from src.tracing import trace_observation, update_observation


RETRY_STATUS_CODES = {429, 502, 503, 529}
# Gemini embedding via OpenRouter rejects batches larger than 100 inputs.
EMBEDDING_BATCH_SIZE = 100


@dataclass
class RerankResult:
    index: int
    relevance_score: float
    text: str


class OpenRouterError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        rerank_model: Optional[str] = None,
        chat_model: Optional[str] = None,
        app_title: Optional[str] = None,
        timeout_seconds: float = 45.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL).rstrip("/")
        self.embedding_model = embedding_model or os.getenv("OPENROUTER_EMBEDDING_MODEL") or OPENROUTER_EMBEDDING_MODEL
        self.rerank_model = rerank_model or os.getenv("OPENROUTER_RERANK_MODEL") or OPENROUTER_RERANK_MODEL
        self.chat_model = chat_model or os.getenv("OPENROUTER_CHAT_MODEL") or OPENROUTER_CHAT_MODEL
        self.app_title = app_title or os.getenv("OPENROUTER_APP_TITLE") or OPENROUTER_APP_TITLE
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        if not self.api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured")

    def embed_texts(
        self,
        texts: List[str],
        input_type: Literal["search_document", "search_query"],
    ) -> List[List[float]]:
        if not texts:
            return []
        embeddings: List[List[float]] = []
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + EMBEDDING_BATCH_SIZE]
            embeddings.extend(self._embed_texts_batch(batch, input_type))
        return embeddings

    def _embed_texts_batch(
        self,
        texts: List[str],
        input_type: Literal["search_document", "search_query"],
    ) -> List[List[float]]:
        payload = {
            "model": self.embedding_model,
            "input": texts,
            "encoding_format": "float",
            "input_type": input_type,
        }
        data = self._post("/embeddings", payload)
        if data.get("error"):
            raise OpenRouterError(f"OpenRouter embeddings failed: {data['error']}")
        embeddings = data.get("data", [])
        if len(embeddings) != len(texts):
            raise OpenRouterError(
                f"OpenRouter embeddings returned {len(embeddings)} vectors for {len(texts)} inputs"
            )
        ordered = sorted(embeddings, key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in ordered]

    def rerank(self, query: str, documents: List[str], top_n: int) -> List[RerankResult]:
        if not documents:
            return []
        payload = {
            "model": self.rerank_model,
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents)),
        }
        data = self._post("/rerank", payload)
        results = []
        for item in data.get("results", []):
            index = int(item["index"])
            document = item.get("document") or {}
            results.append(
                RerankResult(
                    index=index,
                    relevance_score=float(item.get("relevance_score", 0.0)),
                    text=document.get("text") or documents[index],
                )
            )
        return results

    def chat_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        data = self._post("/chat/completions", payload)
        choices = data.get("choices", [])
        if not choices:
            raise OpenRouterError("OpenRouter chat returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenRouterError(f"OpenRouter chat did not return valid JSON: {content[:500]}") from exc
        if not isinstance(parsed, dict):
            raise OpenRouterError("OpenRouter chat JSON response must be an object")
        return parsed

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/abc-co-rag-assistant",
            "X-Title": self.app_title,
        }

        observation_type = "generation" if path == "/chat/completions" else "span"
        with trace_observation(
            f"openrouter{path.replace('/', '-')}",
            input=_safe_openrouter_input(path, payload),
            metadata={"provider": "openrouter", "path": path},
            tags=["openrouter"],
            as_type=observation_type,
            model=str(payload.get("model") or ""),
        ) as observation:
            last_error: Optional[Exception] = None
            for attempt in range(self.max_retries + 1):
                request = urllib.request.Request(url, data=body, headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                        data = json.loads(response.read().decode("utf-8"))
                        update_observation(
                            observation,
                            output=_safe_openrouter_output(path, data),
                            usage_details=_usage_details(data),
                            cost_details=_cost_details(data),
                            metadata={"attempt": attempt + 1, "provider": "openrouter", "path": path},
                        )
                        return data
                except urllib.error.HTTPError as exc:
                    last_error = exc
                    message = exc.read().decode("utf-8", errors="replace")
                    if exc.code not in RETRY_STATUS_CODES or attempt >= self.max_retries:
                        update_observation(
                            observation,
                            output={"error": f"HTTP {exc.code}", "message": message[:500]},
                            metadata={"attempt": attempt + 1, "provider": "openrouter", "path": path},
                        )
                        raise OpenRouterError(f"OpenRouter {path} failed with HTTP {exc.code}: {message}") from exc
                except urllib.error.URLError as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        update_observation(
                            observation,
                            output={"error": "request_failed", "message": str(exc)[:500]},
                            metadata={"attempt": attempt + 1, "provider": "openrouter", "path": path},
                        )
                        raise OpenRouterError(f"OpenRouter {path} request failed: {exc}") from exc

                time.sleep(0.5 * (2**attempt))

            update_observation(
                observation,
                output={"error": "request_failed", "message": str(last_error)[:500]},
                metadata={"provider": "openrouter", "path": path},
            )
            raise OpenRouterError(f"OpenRouter {path} request failed: {last_error}")


def _safe_openrouter_input(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if path == "/embeddings":
        return {
            "model": payload.get("model"),
            "input_count": len(payload.get("input", [])),
            "input_type": payload.get("input_type"),
        }
    if path == "/rerank":
        return {
            "model": payload.get("model"),
            "query": payload.get("query"),
            "document_count": len(payload.get("documents", [])),
            "top_n": payload.get("top_n"),
        }
    if path == "/chat/completions":
        messages = payload.get("messages") or []
        return {
            "model": payload.get("model"),
            "message_count": len(messages),
            "messages": [
                {
                    "role": message.get("role"),
                    "content_chars": len(str(message.get("content", ""))),
                }
                for message in messages
                if isinstance(message, dict)
            ],
            "response_format": payload.get("response_format"),
            "temperature": payload.get("temperature"),
        }
    return {"model": payload.get("model"), "path": path}


def _safe_openrouter_output(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if path == "/embeddings":
        return {"embedding_count": len(data.get("data", []))}
    if path == "/rerank":
        return {"result_count": len(data.get("results", []))}
    if path == "/chat/completions":
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = str(choices[0].get("message", {}).get("content", ""))
        return {"choice_count": len(choices), "content_chars": len(content)}
    return {"keys": sorted(data.keys())}


def _usage_details(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None
    details: Dict[str, Any] = {}
    if "prompt_tokens" in usage:
        details["input_tokens"] = usage["prompt_tokens"]
    if "completion_tokens" in usage:
        details["output_tokens"] = usage["completion_tokens"]
    if "total_tokens" in usage:
        details["total_tokens"] = usage["total_tokens"]
    return details or None


def _cost_details(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    usage = data.get("usage")
    if not isinstance(usage, dict) or "cost" not in usage:
        return None
    return {"total_cost": usage["cost"]}
