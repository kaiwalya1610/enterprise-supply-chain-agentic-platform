from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List

MAX_HISTORY_TURNS = 20


@dataclass
class Message:
    role: str
    content: str
    include_in_context: bool = True


@dataclass
class Session:
    id: str
    history: List[Message] = field(default_factory=list)

    def add(self, role: str, content: str, include_in_context: bool = True) -> Message:
        msg = Message(role=role, content=content, include_in_context=include_in_context)
        self.history.append(msg)
        return msg

    def recent_history(self) -> List[Message]:
        return self.history[-(MAX_HISTORY_TURNS * 2):]

    def context_history(self) -> List[Message]:
        messages = [msg for msg in self.history if msg.include_in_context]
        return messages[-(MAX_HISTORY_TURNS * 2):]


# In-memory store — lost on restart.
_sessions: Dict[str, Session] = {}


def create_session() -> Session:
    session = Session(id=uuid.uuid4().hex[:16])
    _sessions[session.id] = session
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    return _sessions.pop(session_id, None) is not None


def list_sessions() -> List[Session]:
    return list(_sessions.values())
