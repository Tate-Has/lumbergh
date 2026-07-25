import json
import re
from datetime import datetime
from pathlib import Path

from lumbergh.activity.adapter import AgentAdapter
from lumbergh.activity.events import ConversationEvent

# user-text wrappers that are harness noise, not something the user typed
_META_PREFIXES = ("<local-command-caveat>", "<command-name>", "<command-message>")


def _parse_ts(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


def _summarize_tool(name: str, tool_input: dict) -> str:
    tool_input = tool_input or {}
    if name in ("Read", "Edit", "Write", "NotebookEdit"):
        return str(tool_input.get("file_path", ""))
    if name == "Bash":
        return str(tool_input.get("command", ""))
    if name in ("Grep", "Glob"):
        return str(tool_input.get("pattern") or tool_input.get("query") or "")
    if name in ("Task", "Agent"):
        return str(tool_input.get("description", ""))
    return ""


def _stringify_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


class ClaudeCodeAdapter(AgentAdapter):
    def __init__(self, transcript_path: Path):
        self.path = Path(transcript_path)
        self._offset = 0

    @classmethod
    def for_cwd(cls, cwd: Path) -> "ClaudeCodeAdapter | None":
        encoded_cwd = re.sub(r"[^a-zA-Z0-9]", "-", str(cwd))
        project_dir = Path.home() / ".claude" / "projects" / encoded_cwd
        if not project_dir.is_dir():
            return None
        candidates = sorted(
            project_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        return cls(candidates[0])

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
                break  # partial trailing line; wait for the rest
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
        kind = obj.get("type")
        ts = _parse_ts(obj.get("timestamp"))
        message = obj.get("message") or {}
        if kind == "user":
            return self._user_events(message, ts)
        if kind == "assistant":
            return self._assistant_events(message, ts)
        return []

    def _user_events(self, message: dict, ts) -> list[ConversationEvent]:
        content = message.get("content")
        if isinstance(content, str):
            text = content.strip()
            if not text or text.startswith(_META_PREFIXES):
                return []
            return [ConversationEvent(type="user_message", id=self._eid(), timestamp=ts, text=text)]

        events: list[ConversationEvent] = []
        for block in content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                events.append(
                    ConversationEvent(
                        type="user_message",
                        id=self._eid(),
                        timestamp=ts,
                        text=block.get("text", ""),
                    )
                )
            elif block.get("type") == "tool_result":
                events.append(
                    ConversationEvent(
                        type="tool_result",
                        id=self._eid(),
                        timestamp=ts,
                        tool_use_id=block.get("tool_use_id"),
                        status="error" if block.get("is_error") else "ok",
                        text=_stringify_content(block.get("content")),
                    )
                )
        return events

    def _assistant_events(self, message: dict, ts) -> list[ConversationEvent]:
        events: list[ConversationEvent] = []
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "thinking":
                events.append(
                    ConversationEvent(
                        type="thinking",
                        id=self._eid(),
                        timestamp=ts,
                        text=block.get("thinking", ""),
                    )
                )
            elif btype == "text":
                events.append(
                    ConversationEvent(
                        type="agent_message",
                        id=self._eid(),
                        timestamp=ts,
                        text=block.get("text", ""),
                    )
                )
            elif btype == "tool_use":
                name = block.get("name", "")
                tool_input = block.get("input") or {}
                events.append(
                    ConversationEvent(
                        type="tool_call",
                        id=self._eid(),
                        timestamp=ts,
                        tool_name=name,
                        tool_summary=_summarize_tool(name, tool_input),
                        tool_detail=json.dumps(tool_input, indent=2),
                        tool_use_id=block.get("id"),
                    )
                )
        return events

    def _eid(self) -> str:
        self._counter = getattr(self, "_counter", 0) + 1
        return f"ev_{self._counter}"
