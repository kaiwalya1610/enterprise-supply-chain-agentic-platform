from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.config import (
    GUARDRAIL_MIN_QUALITY_SCORE,
    OPENROUTER_BASE_URL,
    OPENROUTER_CHAT_MODEL,
    PROJECT_ROOT,
    SUPPORTED_DATASET_AREAS,
)
from src.models import GuardrailAssessment, RouteDecision
from src.openrouter_client import OpenRouterClient, OpenRouterError


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GUARDRAIL_CONFIG_PATH = PROJECT_ROOT / "guardrails" / "config"
MIN_CONTEXT_RELEVANCE = GUARDRAIL_MIN_QUALITY_SCORE
MIN_GROUNDEDNESS = GUARDRAIL_MIN_QUALITY_SCORE

OUTPUT_REFUSAL = (
    "I cannot provide that answer because it is not sufficiently grounded in the retrieved abc.co sources. "
    "Please ask for a narrower source-grounded answer."
)
INPUT_REFUSAL = "I cannot follow instructions that try to bypass or override the source-grounded assistant rules."

_RENDERED_CONFIG_PATH: Optional[Path] = None

# ---------------------------------------------------------------------------
# Pattern lists
# ---------------------------------------------------------------------------

# Used by route_question() for early routing before retrieval.
PROMPT_INJECTION_PATTERNS = [
    r"\bignore\b.+\b(sop|policy|instructions?|documents?|sources?)\b",
    r"\bdisregard\b.+\b(sop|policy|instructions?|documents?|sources?)\b",
    r"\boverride\b.+\b(instructions?|policy|sop)\b",
    r"\bsay\b.+\b(escalation is never required|refund is always approved)\b",
]

UNSUPPORTED_PATTERNS = [
    r"\bremote work\b",
    r"\bsalary\b|\bcompensation bands?\b|\bpay bands?\b",
    r"\bceo\b.+\b(phone|mobile|personal|contact)\b",
    r"\bpersonal phone\b",
]

# Used by check_input_guardrails() for deeper input blocking.
INPUT_BLOCK_PATTERNS = [
    r"\b(ignore|disregard|override)\b.+\b(instructions?|policy|sop|sources?|documents?|guardrails?)\b",
    r"\b(jailbreak|developer mode|dan mode)\b",
    r"\b(system prompt|hidden prompt|internal instructions?)\b",
    r"\b(tool schema|available tools|function call|tool call arguments?)\b",
    r"\b(call|invoke|execute)\b.+\b(retrieval|inventory|tool)\b.+\b(instead|ignore|bypass)\b",
]

SUPPORTED_BUSINESS_TERMS = [
    "abc",
    "approval",
    "approver",
    "branch",
    "communication",
    "credit",
    "customer",
    "delay",
    "escalation",
    "inventory",
    "kpi",
    "lead time",
    "procurement",
    "purchase",
    "reorder",
    "reorder level",
    "reorder point",
    "refund",
    "shipment",
    "sku",
    "stockout",
    "supplier",
]

# Regex PII detection (email, phone, payment-card-like numbers).
PII_PATTERNS = [
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
    r"\b(?:\+?\d[\s-]?){10,16}\b",
    r"\b(?:\d[ -]*?){13,16}\b",
    r"\b\d{3}-\d{2}-\d{4}\b",
]

# Noise words stripped during heuristic output judging.
STOPWORDS = {
    "a", "about", "above", "all", "an", "and", "answer", "are", "as", "at", "be", "because", "by",
    "can", "citation", "citations", "co", "does", "for", "from", "has", "i", "in", "is", "it", "its",
    "of", "on", "or", "please", "requires", "source", "sources", "that", "the", "this", "to", "with",
}


# ---------------------------------------------------------------------------
# Public routing helpers
# ---------------------------------------------------------------------------

def detect_guardrail_route(question: str) -> Optional[RouteDecision]:
    normalized = question.lower()
    if any(re.search(pattern, normalized) for pattern in PROMPT_INJECTION_PATTERNS):
        return RouteDecision(
            route="guardrail",
            reason="Question attempts to override or ignore source-grounded policy behavior.",
        )
    if any(re.search(pattern, normalized) for pattern in UNSUPPORTED_PATTERNS):
        return RouteDecision(
            route="unsupported",
            reason="Question asks about information not covered by this dataset.",
        )
    return None


def unsupported_message() -> str:
    areas = ", ".join(SUPPORTED_DATASET_AREAS)
    return (
        "The dataset does not contain that information. It is not covered, not available, no information is available, "
        f"and it is not in the documents. Covered areas are: {areas}."
    )


SENSITIVE_REFUSAL = unsupported_message()


def detect_pii(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in PII_PATTERNS)


def _looks_like_supported_business_question(normalized: str) -> bool:
    return any(term in normalized for term in SUPPORTED_BUSINESS_TERMS)


# ---------------------------------------------------------------------------
# NeMo runtime
# ---------------------------------------------------------------------------

def _guardrails_runtime_enabled() -> bool:
    default_enabled = "false" if os.getenv("PYTEST_CURRENT_TEST") else "true"
    return os.getenv("NEMO_GUARDRAILS_ENABLED", default_enabled).strip().lower() not in {"0", "false", "no", "off"}


def _prepare_nemo_env() -> None:
    os.environ.setdefault("OPENROUTER_GUARDRAIL_MODEL", os.getenv("OPENROUTER_CHAT_MODEL") or OPENROUTER_CHAT_MODEL)
    os.environ.setdefault("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)


def _render_config_dir() -> Path:
    global _RENDERED_CONFIG_PATH
    if _RENDERED_CONFIG_PATH and _RENDERED_CONFIG_PATH.exists():
        return _RENDERED_CONFIG_PATH

    _prepare_nemo_env()
    target = Path(tempfile.mkdtemp(prefix="abc_guardrails_"))
    shutil.copytree(GUARDRAIL_CONFIG_PATH, target, dirs_exist_ok=True)
    replacements = {
        "${OPENROUTER_GUARDRAIL_MODEL}": os.environ["OPENROUTER_GUARDRAIL_MODEL"],
        "${OPENROUTER_BASE_URL}": os.environ["OPENROUTER_BASE_URL"],
        "model: deepseek/deepseek-v4-pro": f"model: {os.environ['OPENROUTER_GUARDRAIL_MODEL']}",
        "base_url: https://openrouter.ai/api/v1": f"base_url: {os.environ['OPENROUTER_BASE_URL']}",
    }
    for path in target.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".yml", ".yaml", ".co"}:
            continue
        text = path.read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, value)
        path.write_text(text, encoding="utf-8")

    _RENDERED_CONFIG_PATH = target
    return target


@lru_cache(maxsize=1)
def _load_rails() -> Any:
    try:
        from nemoguardrails import LLMRails, RailsConfig
    except ImportError as exc:
        raise RuntimeError("nemoguardrails is not installed") from exc

    config = RailsConfig.from_path(str(_render_config_dir()))
    return LLMRails(config)


def _run_nemo_input_check(question: str) -> Optional[str]:
    if not _guardrails_runtime_enabled():
        return None
    try:
        rails = _load_rails()
        response = rails.generate(messages=[{"role": "user", "content": question}])
    except Exception as exc:
        return f"NeMo input rails unavailable: {exc}"

    content = str(response.get("content", "") if isinstance(response, dict) else response).lower()
    if "can't respond" in content or "cannot respond" in content or "can't assist" in content:
        return "nemo_input"
    return None


def _run_nemo_output_check(question: str, answer: str, retrieved_context: Dict[str, Any]) -> Optional[str]:
    if not _guardrails_runtime_enabled():
        return None
    try:
        rails = _load_rails()
        rails.generate(
            messages=[
                {"role": "context", "content": {"retrieved_context": retrieved_context}},
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        )
    except Exception as exc:
        return f"NeMo output rails unavailable: {exc}"
    return None


# ---------------------------------------------------------------------------
# Input guardrails
# ---------------------------------------------------------------------------

def check_input_guardrails(question: str, run_nemo: bool = True) -> GuardrailAssessment:
    normalized = question.lower()
    deterministic_route = detect_guardrail_route(question)
    if deterministic_route and deterministic_route.route == "guardrail":
        return GuardrailAssessment(
            allowed=False,
            triggered_input_rail="deterministic_prompt_injection",
            hallucination_reasons=[deterministic_route.reason],
        )
    if deterministic_route and deterministic_route.route == "unsupported":
        return GuardrailAssessment(
            allowed=False,
            triggered_input_rail="deterministic_unsupported_sensitive_request",
            hallucination_reasons=[deterministic_route.reason],
        )
    if any(re.search(pattern, normalized) for pattern in INPUT_BLOCK_PATTERNS):
        return GuardrailAssessment(
            allowed=False,
            triggered_input_rail="input_policy",
            hallucination_reasons=["The request attempts to bypass instructions or expose tool/system internals."],
        )
    if detect_pii(question):
        return GuardrailAssessment(
            allowed=False,
            triggered_input_rail="regex_pii",
            hallucination_reasons=["The request contains likely personal or sensitive data."],
        )
    if _looks_like_supported_business_question(normalized):
        return GuardrailAssessment(allowed=True)

    if not run_nemo:
        return GuardrailAssessment(allowed=True)

    nemo_result = _run_nemo_input_check(question)
    if nemo_result == "nemo_input":
        return GuardrailAssessment(
            allowed=False,
            triggered_input_rail="nemo_input",
            hallucination_reasons=["NeMo input rails blocked the request."],
        )
    warnings = [nemo_result] if nemo_result else []
    return GuardrailAssessment(allowed=True, warnings=warnings)


# ---------------------------------------------------------------------------
# Output guardrails
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    return [token for token in re.findall(r"[A-Za-z0-9₹,]+", text.lower()) if token not in STOPWORDS and len(token) > 2]


def _clamp_score(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def _normalise_judge_payload(data: Dict[str, Any]) -> GuardrailAssessment:
    context_relevance = _clamp_score(data.get("context_relevance_score"), 1.0)
    groundedness = _clamp_score(data.get("groundedness_score"), 1.0)
    hallucination_detected = bool(data.get("hallucination_detected", False))
    reasons = data.get("hallucination_reasons") or data.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    allowed = bool(data.get("allowed", True))
    if context_relevance < MIN_CONTEXT_RELEVANCE or groundedness < MIN_GROUNDEDNESS or hallucination_detected:
        allowed = False
    return GuardrailAssessment(
        allowed=allowed,
        context_relevance_score=context_relevance,
        groundedness_score=groundedness,
        hallucination_detected=hallucination_detected,
        hallucination_reasons=[str(reason) for reason in reasons],
        triggered_output_rail=None if allowed else "context_relevance_and_hallucination",
    )


def _judge_with_openrouter(question: str, answer: str, retrieved_context: Dict[str, Any]) -> GuardrailAssessment:
    default_enabled = "false" if os.getenv("PYTEST_CURRENT_TEST") else "true"
    if os.getenv("OPENROUTER_GUARDRAIL_JUDGE_ENABLED", default_enabled).strip().lower() not in {
        "1", "true", "yes", "on",
    }:
        raise OpenRouterError("OpenRouter guardrail judge is disabled by environment.")

    client = OpenRouterClient(chat_model=os.getenv("OPENROUTER_GUARDRAIL_MODEL") or OPENROUTER_CHAT_MODEL)
    system_prompt = (
        "You are a strict RAG output guardrail. Return JSON only with keys: allowed, "
        "context_relevance_score, groundedness_score, hallucination_detected, hallucination_reasons. "
        "Score context_relevance by whether the retrieved context answers the user question. "
        "Score groundedness by whether every factual claim in the final answer is supported by the retrieved context. "
        "Set hallucination_detected true when the answer adds unsupported operational facts."
    )
    user_payload = {
        "user_question": question,
        "final_answer": answer,
        "retrieved_context": retrieved_context,
        "thresholds": {
            "minimum_context_relevance_score": MIN_CONTEXT_RELEVANCE,
            "minimum_groundedness_score": MIN_GROUNDEDNESS,
        },
    }
    data = client.chat_json(system_prompt, json.dumps(user_payload, ensure_ascii=False))
    return _normalise_judge_payload(data)


def _missing_numbers(answer: str, context_text: str, question: str) -> List[str]:
    context_and_question = f"{context_text}\n{question}"
    missing = []
    for number in re.findall(r"(?:₹|rs\.?|inr)?\s*\d[\d,]*(?:\.\d+)?", answer.lower()):
        value = number.strip()
        if value and value not in context_and_question.lower():
            missing.append(value)
    return missing


def _missing_proper_terms(answer: str, context_text: str, question: str) -> List[str]:
    known = f"{context_text}\n{question}".lower()
    ignored = {"ABC", "Citations", "Citation", "Route", "Confidence", "Model", "The", "This", "Please", "I"}
    missing = []
    for term in re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", answer):
        if term in ignored:
            continue
        if term.lower() not in known:
            missing.append(term)
    return sorted(set(missing))


def _heuristic_output_judge(question: str, answer: str, retrieved_context: Dict[str, Any]) -> GuardrailAssessment:
    from src.tools import retrieved_text_for_guardrails

    context_text = retrieved_text_for_guardrails(retrieved_context)
    if not context_text:
        return GuardrailAssessment(allowed=True, warnings=["No retrieved context was supplied for output scoring."])

    context_tokens = set(_tokenize(context_text))
    question_tokens = set(_tokenize(question))
    answer_tokens = set(_tokenize(answer))
    context_relevance = 1.0 if context_tokens & question_tokens else 0.5

    unsupported_tokens = answer_tokens - context_tokens - question_tokens
    token_penalty = min(len(unsupported_tokens) / max(len(answer_tokens), 1), 0.35)
    groundedness = max(0.0, 1.0 - token_penalty)

    missing_numbers = _missing_numbers(answer, context_text, question)
    missing_terms = _missing_proper_terms(answer, context_text, question)
    reasons: List[str] = []
    if missing_numbers:
        reasons.append(f"Numbers absent from retrieved context: {', '.join(missing_numbers[:5])}.")
    if missing_terms:
        reasons.append(f"Named terms absent from retrieved context: {', '.join(missing_terms[:5])}.")

    hallucination_detected = bool(missing_numbers or missing_terms)
    if hallucination_detected:
        groundedness = min(groundedness, 0.6)
    allowed = (
        context_relevance >= MIN_CONTEXT_RELEVANCE
        and groundedness >= MIN_GROUNDEDNESS
        and not hallucination_detected
    )
    return GuardrailAssessment(
        allowed=allowed,
        context_relevance_score=context_relevance,
        groundedness_score=groundedness,
        hallucination_detected=hallucination_detected,
        hallucination_reasons=reasons,
        triggered_output_rail=None if allowed else "context_relevance_and_hallucination",
        warnings=["OpenRouter guardrail judge unavailable; used local heuristic fallback."],
    )


def check_output_guardrails(
    question: str,
    answer: str,
    retrieved_context: Dict[str, Any],
    run_nemo: bool = True,
) -> GuardrailAssessment:
    if detect_pii(answer):
        return GuardrailAssessment(
            allowed=False,
            triggered_output_rail="regex_pii",
            hallucination_reasons=["The answer contains likely personal or sensitive data."],
        )

    warnings: List[str] = []
    if run_nemo:
        nemo_warning = _run_nemo_output_check(question, answer, retrieved_context)
        if nemo_warning:
            warnings.append(nemo_warning)

    try:
        assessment = _judge_with_openrouter(question, answer, retrieved_context)
    except (OpenRouterError, ValueError, TypeError) as exc:
        assessment = _heuristic_output_judge(question, answer, retrieved_context)
        assessment.warnings.append(str(exc))

    assessment.warnings = [*warnings, *assessment.warnings]
    return assessment


def needs_quality_retry(
    assessment: GuardrailAssessment,
    threshold: Optional[float] = None,
) -> bool:
    limit = GUARDRAIL_MIN_QUALITY_SCORE if threshold is None else threshold
    return (
        assessment.hallucination_detected
        or assessment.context_relevance_score < limit
        or assessment.groundedness_score < limit
    )


def quality_retry_eligible(
    assessment: GuardrailAssessment,
    threshold: Optional[float] = None,
) -> bool:
    if assessment.triggered_output_rail == "regex_pii":
        return False
    return needs_quality_retry(assessment, threshold)


def guarded_output(answer: str, assessment: GuardrailAssessment) -> str:
    return answer if assessment.allowed else OUTPUT_REFUSAL


def combine_assessment_warnings(assessments: Iterable[GuardrailAssessment]) -> List[str]:
    warnings: List[str] = []
    for assessment in assessments:
        warnings.extend(assessment.warnings)
    return warnings
