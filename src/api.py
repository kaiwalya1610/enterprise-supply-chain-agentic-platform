from __future__ import annotations

import json
import inspect
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.config import PROJECT_ROOT
from src.llm_interface import (
    LLMInterfaceError,
    LLMInterfaceResult,
    answer_with_llm,
    answer_with_llm_events,
    build_workflow,
    create_openrouter_llm,
)
from src.session import (
    Session,
    create_session,
    delete_session,
    get_session,
    list_sessions,
)

app = FastAPI(title="abc.co Supply Chain Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_llm = None
_workflow = None


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env", override=False)
    except ImportError:
        pass


@app.on_event("startup")
def startup() -> None:
    global _llm, _workflow
    _load_env()
    _llm = create_openrouter_llm()
    _workflow = build_workflow(_llm)


# --- Request / Response models ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    route: str
    confidence: str
    citations: List[Dict[str, Any]]
    warnings: List[str]
    model: str
    guardrail: Dict[str, Any]


class SessionResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]


# --- Endpoints ---

def _chat_response(session_id: str, result: LLMInterfaceResult) -> ChatResponse:
    assessment = result.guardrail_assessment
    return ChatResponse(
        session_id=session_id,
        answer=result.answer,
        route=result.route,
        confidence=result.confidence,
        citations=[asdict(c) for c in result.citations],
        warnings=result.warnings,
        model=result.model,
        guardrail={
            "context_relevance_score": assessment.context_relevance_score,
            "groundedness_score": assessment.groundedness_score,
            "hallucination_detected": assessment.hallucination_detected,
            "triggered_input_rail": assessment.triggered_input_rail,
            "triggered_output_rail": assessment.triggered_output_rail,
        },
    )


def _chat_response_dict(session_id: str, result: LLMInterfaceResult) -> Dict[str, Any]:
    response = _chat_response(session_id, result)
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response.dict()


def _include_turn_in_context(result: LLMInterfaceResult) -> bool:
    assessment = result.guardrail_assessment
    return not (
        result.route == "guardrail"
        or assessment.triggered_input_rail
        or assessment.triggered_output_rail
    )


def _sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _supports_trace_session_id(func: Any) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return True
    return "trace_session_id" in signature.parameters


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if req.session_id:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
    else:
        session = create_session()

    history = [{"role": m.role, "content": m.content} for m in session.context_history()]

    try:
        result = answer_with_llm(
            req.message.strip(),
            llm=_llm,
            workflow=_workflow,
            history=history,
            **({"trace_session_id": session.id} if _supports_trace_session_id(answer_with_llm) else {}),
        )
    except LLMInterfaceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    include_turn_in_context = _include_turn_in_context(result)
    session.add("user", req.message.strip(), include_in_context=include_turn_in_context)
    session.add("assistant", result.answer, include_in_context=include_turn_in_context)

    return _chat_response(session.id, result)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if req.session_id:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
    else:
        session = create_session()

    history = [{"role": m.role, "content": m.content} for m in session.context_history()]
    message = req.message.strip()

    def event_stream():
        yield _sse({"type": "session", "session_id": session.id})
        final_result: Optional[LLMInterfaceResult] = None
        try:
            for event in answer_with_llm_events(
                message,
                llm=_llm,
                history=history,
                **({"trace_session_id": session.id} if _supports_trace_session_id(answer_with_llm_events) else {}),
            ):
                if event["type"] == "done":
                    final_result = event["result"]
                    yield _sse({
                        "type": "done",
                        **_chat_response_dict(session.id, final_result),
                    })
                else:
                    yield _sse(event)
        except LLMInterfaceError as exc:
            yield _sse({"type": "error", "detail": str(exc)})
            return

        if final_result is None:
            return

        include_turn_in_context = _include_turn_in_context(final_result)
        session.add("user", message, include_in_context=include_turn_in_context)
        session.add("assistant", final_result.answer, include_in_context=include_turn_in_context)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/sessions", response_model=SessionResponse)
def create_new_session() -> SessionResponse:
    session = create_session()
    return _session_response(session)


@app.get("/sessions", response_model=SessionListResponse)
def get_sessions() -> SessionListResponse:
    return SessionListResponse(
        sessions=[_session_response(s) for s in list_sessions()]
    )


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session_detail(session_id: str) -> SessionResponse:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _session_response(session)


@app.delete("/sessions/{session_id}")
def remove_session(session_id: str) -> dict:
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"deleted": True}


def _session_response(session: Session) -> SessionResponse:
    return SessionResponse(
        session_id=session.id,
        messages=[ChatMessage(role=m.role, content=m.content) for m in session.history],
    )
