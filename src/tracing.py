from __future__ import annotations

import atexit
import os
from contextlib import contextmanager, nullcontext
from typing import Any, Dict, Iterator, Optional


_CLIENT: Any = None
_CLIENT_INITIALIZED = False


def _has_langfuse_credentials() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def langfuse_enabled() -> bool:
    return _has_langfuse_credentials() and os.getenv("LANGFUSE_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def get_langfuse_client() -> Optional[Any]:
    global _CLIENT, _CLIENT_INITIALIZED
    if not langfuse_enabled():
        return None
    if os.getenv("LANGFUSE_HOST") and not os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_BASE_URL"] = os.environ["LANGFUSE_HOST"]
    if _CLIENT_INITIALIZED:
        return _CLIENT
    _CLIENT_INITIALIZED = True
    try:
        from langfuse import get_client
    except ImportError:
        return None
    _CLIENT = get_client()
    return _CLIENT


def flush_langfuse() -> None:
    client = get_langfuse_client()
    if client is None:
        return
    flush = getattr(client, "flush", None)
    if callable(flush):
        flush()


atexit.register(flush_langfuse)


def langfuse_callback_config() -> Optional[Dict[str, Any]]:
    if not langfuse_enabled():
        return None
    try:
        from langfuse.langchain import CallbackHandler
    except ImportError:
        return None
    return {"callbacks": [CallbackHandler()]}


@contextmanager
def trace_observation(
    name: str,
    *,
    input: Optional[Any] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
    as_type: str = "span",
    model: Optional[str] = None,
) -> Iterator[Optional[Any]]:
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        from langfuse import propagate_attributes
    except ImportError:
        yield None
        return

    observation_args: Dict[str, Any] = {
        "as_type": as_type,
        "name": name,
    }
    if input is not None:
        observation_args["input"] = input
    if model:
        observation_args["model"] = model

    propagated_metadata = None
    if metadata:
        propagated_metadata = {key: str(value) for key, value in metadata.items()}

    attributes = {
        "trace_name": name,
        "metadata": propagated_metadata,
        "tags": tags,
        "session_id": session_id,
    }
    attributes = {key: value for key, value in attributes.items() if value}

    with client.start_as_current_observation(**observation_args) as observation:
        with propagate_attributes(**attributes) if attributes else nullcontext():
            yield observation


def update_observation(observation: Optional[Any], **kwargs: Any) -> None:
    if observation is None:
        return
    update = getattr(observation, "update", None)
    if callable(update):
        update(**{key: value for key, value in kwargs.items() if value is not None})
