"""Pi transcript adapter — same shape as Claude's, reading ~/.pi/agent/sessions.

Pi writes JSONL sessions bucketed by an encoded cwd; message events carry
{role, content:[...]} with text/thinking/toolCall blocks and toolResult messages.
"""

import json
from pathlib import Path

from lumbergh.activity.adapter import AgentAdapter
from lumbergh.activity.claude_code import _parse_ts, _stringify_content
from lumbergh.activity.events import ConversationEvent


def _summarize_pi_tool(name: str, args: dict) -> str:
    args = args or {}
    if name in ("bash", "shell"):
        return str(args.get("command", ""))
    if name in ("read", "write", "edit"):
        return str(args.get("path") or args.get("file_path") or "")
    if name in ("grep", "glob", "search"):
        return str(args.get("pattern") or args.get("query") or "")
    return ""


class PiAdapter(AgentAdapter):
    SESSIONS_DIR = Path.home() / ".pi" / "agent" / "sessions"

    def __init__(self, transcript_path: Path, root: Path | None = None):
        self.path = Path(transcript_path)
        self.root = Path(root) if root else None
        self._offset = 0
        self._counter = 0

    @classmethod
    def for_cwd(cls, cwd) -> "PiAdapter | None":
        encoded = "-" + str(cwd).replace("/", "-") + "--"
        session_dir = cls.SESSIONS_DIR / encoded
        if not session_dir.is_dir():
            return None
        candidates = sorted(
            session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        return cls(candidates[0], root=cwd) if candidates else None

    @classmethod
    def resolve(cls, session_name: str, cwd) -> "PiAdapter | None":  # noqa: ARG003 - interface parity (Pi has no identity hook yet)
        return cls.for_cwd(cwd) if cwd is not None else None

    def _eid(self) -> str:
        self._counter += 1
        return f"pi_{self._counter}"

    def _source_signature(self) -> tuple[int, float]:
        try:
            st = self.path.stat()
            return (st.st_size, st.st_mtime)
        except OSError:
            return (-1, -1.0)

    def read_new(self) -> list[ConversationEvent]:
        try:
            with self.path.open("rb") as f:
                f.seek(self._offset)
                data = f.read()
        except OSError:
            return []
        events: list[ConversationEvent] = []
        consumed = 0
        for raw in data.splitlines(keepends=True):
            if not raw.endswith(b"\n"):
                break
            consumed += len(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.extend(self._events_from_line(obj))
        self._offset += consumed
        return events

    def _events_from_line(self, obj: dict) -> list[ConversationEvent]:
        if obj.get("type") != "message":
            return []
        message = obj.get("message") or {}
        ts = _parse_ts(obj.get("timestamp"))
        role = message.get("role")
        if role == "user":
            return self._blocks_to_events(message.get("content"), ts, assistant=False)
        if role == "assistant":
            return self._blocks_to_events(message.get("content"), ts, assistant=True)
        if role == "toolResult":
            return [
                ConversationEvent(
                    type="tool_result",
                    id=self._eid(),
                    timestamp=ts,
                    tool_use_id=message.get("toolCallId"),
                    tool_name=message.get("toolName"),
                    status="ok",
                    text=_stringify_content(message.get("content")),
                )
            ]
        return []

    def _blocks_to_events(self, content, ts, assistant: bool) -> list[ConversationEvent]:
        events: list[ConversationEvent] = []
        for block in content or []:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                events.append(
                    ConversationEvent(
                        type="agent_message" if assistant else "user_message",
                        id=self._eid(),
                        timestamp=ts,
                        text=block.get("text", ""),
                    )
                )
            elif btype == "thinking" and assistant:
                events.append(
                    ConversationEvent(
                        type="thinking",
                        id=self._eid(),
                        timestamp=ts,
                        text=block.get("thinking", ""),
                    )
                )
            elif btype == "toolCall" and assistant:
                name = block.get("name", "")
                args = block.get("arguments") or {}
                events.append(
                    ConversationEvent(
                        type="tool_call",
                        id=self._eid(),
                        timestamp=ts,
                        tool_name=name,
                        tool_summary=_summarize_pi_tool(name, args),
                        tool_detail=json.dumps(args, indent=2),
                        tool_use_id=block.get("id"),
                    )
                )
        return events
