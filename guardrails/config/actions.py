from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from nemoguardrails.actions import action
except ImportError:
    def action(*_args: Any, **_kwargs: Any):
        def decorator(func):
            return func

        return decorator

from src.guardrails import (
    check_input_guardrails,
    check_output_guardrails,
    detect_pii,
)


@action(is_system_action=True)
async def check_regex_pii_input(context: Optional[Dict[str, Any]] = None) -> bool:
    """Return true when regex PII patterns match the user message."""
    active_context = context or {}
    user_message = active_context.get("last_user_message") or active_context.get("user_message") or ""
    return detect_pii(str(user_message))


@action(is_system_action=True)
async def check_regex_pii_output(context: Optional[Dict[str, Any]] = None) -> bool:
    """Return true when regex PII patterns match the assistant response."""
    active_context = context or {}
    answer = active_context.get("bot_message") or active_context.get("last_bot_message") or ""
    return detect_pii(str(answer))


@action(is_system_action=True)
async def check_unsafe_input(context: Optional[Dict[str, Any]] = None) -> bool:
    """Return true when deterministic or NeMo input rails should block the user message."""
    active_context = context or {}
    user_message = active_context.get("last_user_message") or active_context.get("user_message") or ""
    assessment = check_input_guardrails(str(user_message), run_nemo=False)
    active_context["abc_input_guardrail_assessment"] = assessment.__dict__
    return not assessment.allowed


@action(is_system_action=True)
async def check_context_relevance_and_hallucination(context: Optional[Dict[str, Any]] = None) -> bool:
    """Return true when the current bot response is not grounded in retrieved context."""
    active_context = context or {}
    question = active_context.get("last_user_message") or active_context.get("user_message") or ""
    answer = active_context.get("bot_message") or active_context.get("last_bot_message") or ""
    retrieved_context = active_context.get("retrieved_context") or active_context.get("context") or {}
    if isinstance(retrieved_context, str):
        retrieved_context = {"doc_chunks": [{"text": retrieved_context}]}

    assessment = check_output_guardrails(str(question), str(answer), retrieved_context, run_nemo=False)
    active_context["abc_output_guardrail_assessment"] = assessment.__dict__
    return not assessment.allowed
