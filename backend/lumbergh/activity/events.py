from typing import Literal

from pydantic import BaseModel

EventType = Literal[
    "user_message",
    "agent_message",
    "thinking",
    "tool_call",
    "tool_result",
    "status",
]


class ConversationEvent(BaseModel):
    """Agent-agnostic conversation event. The frontend renderer sees only this."""

    type: EventType
    id: str
    timestamp: float | None = None
    # user_message / agent_message / thinking / status
    text: str | None = None
    # tool_call
    tool_name: str | None = None
    tool_summary: str | None = None
    tool_detail: str | None = None
    # tool_call (its id) and tool_result (the call it answers)
    tool_use_id: str | None = None
    # tool_result: "ok" | "error"
    status: str | None = None
