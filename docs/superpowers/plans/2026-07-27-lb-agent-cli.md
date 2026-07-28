# `lb` Agent-Facing Control CLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `lb`, an AXI CLI (installed with `pylumbergh`) that lets an agent observe and coordinate Lumbergh sessions — `lb` (list), `read` (structured transcript, Claude + Pi), `state`, `wait --until`, `prompt`.

**Architecture:** `lb` is a thin HTTP client to a new localhost-token-gated `/api/agent/*` backend surface. State/wait serve from in-memory monitor state (no DB race); `read` reuses the activity adapters (`ClaudeCodeAdapter`; new `PiAdapter`); pane/send via `tmux_pty`. Output is TOON.

**Tech Stack:** Python 3.11+, FastAPI, pytest; TOON output. No new runtime deps.

## Global Constraints

- Python 3.11+; no new dependencies. TOON is a tiny in-repo renderer.
- `/api/agent/*` is auth-exempt **only** with a valid `X-Lumbergh-Agent-Token` header (token file `~/.config/lumbergh/agent-token`, mode 0600). A loopback-IP check is insufficient (the cloud tunnel proxies via localhost).
- The CLI reaches the backend over HTTP; connection-refused → the AXI "server not running" error (this is the "only works when the server is on" gate).
- AXI compliance is mandatory: TOON on **stdout**; diagnostics on stderr; exit **0** success/no-op, **1** operational error, **2** usage error; unknown flags rejected by name with valid flags inlined; no-args shows live data; structured errors on stdout.
- Default session target = `$LUMBERGH_SESSION`; `--session` overrides; `--help` always allowed.
- Run `./lint.sh` clean. Do not commit `.agents/`, `.claude/skills/`, `skills-lock.json`, or `frontend/package-lock.json`.
- Commit messages: no AI attribution / Co-Authored-By lines.

---

### Task 1: Agent token

**Files:**
- Modify: `backend/lumbergh/constants.py` (add `AGENT_TOKEN_FILE`)
- Create: `backend/lumbergh/agent_token.py`
- Test: `backend/lumbergh/tests/test_agent_token.py`

**Interfaces:**
- `AGENT_TOKEN_FILE: Path` = `CONFIG_DIR / "agent-token"`.
- `ensure_token() -> str` — create with `secrets.token_urlsafe(32)` at mode 0600 if absent; return the token.
- `read_token() -> str | None` — the stored token or None.
- `verify(candidate: str | None) -> bool` — constant-time compare against the stored token; False if no token or no candidate.

- [ ] **Step 1: Add the constant**

In `constants.py`, after `SESSION_ATTENTION_FILE`:

```python
AGENT_TOKEN_FILE = CONFIG_DIR / "agent-token"
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/lumbergh/tests/test_agent_token.py
import lumbergh.agent_token as at


def test_ensure_creates_token_0600(tmp_path, monkeypatch):
    path = tmp_path / "agent-token"
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", path)
    tok = at.ensure_token()
    assert tok and path.exists()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert at.ensure_token() == tok  # stable across calls


def test_read_and_verify(tmp_path, monkeypatch):
    path = tmp_path / "agent-token"
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", path)
    tok = at.ensure_token()
    assert at.read_token() == tok
    assert at.verify(tok) is True
    assert at.verify("nope") is False
    assert at.verify(None) is False


def test_verify_no_token_file(tmp_path, monkeypatch):
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", tmp_path / "absent")
    assert at.verify("anything") is False
    assert at.read_token() is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_token.py -q`
Expected: FAIL — no module `lumbergh.agent_token`.

- [ ] **Step 4: Implement `agent_token.py`**

```python
# backend/lumbergh/agent_token.py
"""Local token gating the /api/agent surface.

The token file is readable only by the local user, so only local processes can
call the agent API — secure even when the cloud tunnel proxies requests over
localhost (an IP check could not tell those apart).
"""

import hmac
import os
import secrets

from lumbergh.constants import AGENT_TOKEN_FILE


def ensure_token() -> str:
    existing = read_token()
    if existing:
        return existing
    AGENT_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    fd = os.open(str(AGENT_TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    return token


def read_token() -> str | None:
    try:
        return AGENT_TOKEN_FILE.read_text().strip() or None
    except OSError:
        return None


def verify(candidate: str | None) -> bool:
    stored = read_token()
    if not stored or not candidate:
        return False
    return hmac.compare_digest(stored, candidate)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_token.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/constants.py backend/lumbergh/agent_token.py backend/lumbergh/tests/test_agent_token.py
git commit -m "feat(agent): local token for the agent API"
```

---

### Task 2: Auth exemption for `/api/agent`

**Files:**
- Modify: `backend/lumbergh/auth.py` (`AuthMiddleware.__call__`)
- Test: `backend/lumbergh/tests/test_agent_auth.py`

**Interfaces:** none new. Behavior: a request to a path starting `/api/agent` with header `x-lumbergh-agent-token` matching the stored token passes without cookie auth; without a valid token it falls through to normal auth (401).

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_agent_auth.py
import asyncio

import lumbergh.agent_token as at
from lumbergh.auth import AuthMiddleware


def _scope(path, headers=None):
    return {"type": "http", "path": path, "headers": headers or []}


async def _passes(mw, scope):
    called = {"app": False}

    async def app(s, r, snd):
        called["app"] = True

    async def send(msg):
        called.setdefault("status", None)
        if msg["type"] == "http.response.start":
            called["status"] = msg["status"]

    mw.app = app
    await mw(scope, None, send)
    return called


def test_agent_path_with_valid_token_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", tmp_path / "t")
    tok = at.ensure_token()
    monkeypatch.setattr("lumbergh.auth._is_auth_enabled", lambda: True)
    mw = AuthMiddleware(app=None)
    scope = _scope("/api/agent/sessions", [(b"x-lumbergh-agent-token", tok.encode())])
    assert asyncio.run(_passes(mw, scope))["app"] is True


def test_agent_path_without_token_is_401(tmp_path, monkeypatch):
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", tmp_path / "t")
    at.ensure_token()
    monkeypatch.setattr("lumbergh.auth._is_auth_enabled", lambda: True)
    mw = AuthMiddleware(app=None)
    res = asyncio.run(_passes(mw, _scope("/api/agent/sessions", [])))
    assert res["app"] is False
    assert res["status"] == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_auth.py -q`
Expected: FAIL — agent path currently hits the cookie path → 401 even with token.

- [ ] **Step 3: Add the exemption**

In `auth.py`, add the import near the top:

```python
from lumbergh import agent_token
```

In `__call__`, immediately after the existing allow-list block (`if path.startswith("/api/auth") or path == "/api/health" or not path.startswith("/api/"): return await self.app(...)`), add:

```python
        # Local agent CLI: a valid agent token gates /api/agent (see agent_token).
        if path.startswith("/api/agent"):
            for key, val in scope.get("headers", []):
                if key == b"x-lumbergh-agent-token" and agent_token.verify(val.decode()):
                    return await self.app(scope, receive, send)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_auth.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/auth.py backend/lumbergh/tests/test_agent_auth.py
git commit -m "feat(agent): token-gated auth exemption for /api/agent"
```

---

### Task 3: `state_since` on the monitor

**Files:**
- Modify: `backend/lumbergh/idle_monitor.py`
- Test: `backend/lumbergh/tests/test_idle_monitor_state_since.py`

**Interfaces:** `IdleMonitor.state_since_seconds(name: str) -> float | None` — seconds since the session's state last changed, or None if unknown.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_idle_monitor_state_since.py
import lumbergh.idle_monitor as im


def test_state_since_tracked_on_change(monkeypatch):
    monitor = im.IdleMonitor()
    t = [1000.0]
    monkeypatch.setattr(im.time, "time", lambda: t[0])
    monitor._record_state_change("s", im.SessionState.WORKING)
    t[0] = 1005.0
    assert 4.9 < monitor.state_since_seconds("s") < 5.1
    assert monitor.state_since_seconds("unknown") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_state_since.py -q`
Expected: FAIL — `_record_state_change`/`state_since_seconds` don't exist.

- [ ] **Step 3: Implement**

In `IdleMonitor.__init__`, add:

```python
        self._state_since: dict[str, float] = {}
```

Add two methods:

```python
    def _record_state_change(self, session_name: str, state: SessionState) -> None:
        self._states[session_name] = state
        self._state_since[session_name] = time.time()

    def state_since_seconds(self, session_name: str) -> float | None:
        started = self._state_since.get(session_name)
        return None if started is None else time.time() - started
```

In `_check_session`, inside the transition block, replace `self._states[session_name] = state` with `self._record_state_change(session_name, state)`. In `_check_all_sessions`'s dead-session cleanup loop, add `self._state_since.pop(name, None)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_state_since.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/idle_monitor.py backend/lumbergh/tests/test_idle_monitor_state_since.py
git commit -m "feat(agent): track time-in-state on the monitor"
```

---

### Task 4: Clean pane capture + send-text helpers

**Files:**
- Modify: `backend/lumbergh/tmux_pty.py`
- Test: `backend/lumbergh/tests/test_tmux_agent_helpers.py`

**Interfaces:**
- `capture_pane_text(session_name: str, lines: int | None = None) -> str` — plain (no-ANSI, newline-separated) pane text via `tmux capture-pane -p` (`-S -lines` for scrollback). `""` on failure.
- `send_text(session_name: str, text: str) -> bool` — `send-keys -l -- <text>` then `send-keys Enter`; True on success.

**Notes:** `capture_pane_content` re-emits with cursor-positioning escapes (unusable for reading); this is the clean-text primitive.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_tmux_agent_helpers.py
import subprocess
from unittest.mock import patch

from lumbergh.tmux_pty import capture_pane_text, send_text


def _ok(stdout=""):
    return subprocess.CompletedProcess([], 0, stdout=stdout)


def test_capture_pane_text_returns_plain(monkeypatch):
    with patch("lumbergh.tmux_pty.subprocess.run", return_value=_ok("line1\nline2\n")):
        assert capture_pane_text("s") == "line1\nline2"


def test_capture_pane_text_failure_returns_empty():
    with patch("lumbergh.tmux_pty.subprocess.run", side_effect=OSError):
        assert capture_pane_text("s") == ""


def test_send_text_sends_literal_then_enter():
    calls = []
    with patch("lumbergh.tmux_pty.subprocess.run", side_effect=lambda cmd, **k: calls.append(cmd) or _ok()):
        assert send_text("s", "hello world") is True
    assert any("-l" in c and "hello world" in c for c in calls)
    assert any(c[-1] == "Enter" for c in calls)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_tmux_agent_helpers.py -q`
Expected: FAIL — helpers don't exist.

- [ ] **Step 3: Implement (append to `tmux_pty.py`)**

```python
def capture_pane_text(session_name: str, lines: int | None = None) -> str:
    """Plain, newline-separated pane text (no ANSI) — for reading, not rendering."""
    cmd = [TMUX_CMD, "capture-pane", "-t", session_name, "-p"]
    if lines:
        cmd += ["-S", str(-lines)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=5
        )
        if result.returncode != 0:
            return ""
        return result.stdout.rstrip("\n")
    except Exception:
        return ""


def send_text(session_name: str, text: str) -> bool:
    """Type a line of input into the session's pane (literal text, then Enter)."""
    try:
        for args in (["send-keys", "-t", session_name, "-l", "--", text],
                     ["send-keys", "-t", session_name, "Enter"]):
            r = subprocess.run(
                [TMUX_CMD, *args], capture_output=True, encoding="utf-8", errors="replace", timeout=5
            )
            if r.returncode != 0:
                return False
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_tmux_agent_helpers.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/tmux_pty.py backend/lumbergh/tests/test_tmux_agent_helpers.py
git commit -m "feat(agent): clean pane-text capture and send-text helpers"
```

---

### Task 5: `PiAdapter`

**Files:**
- Create: `backend/lumbergh/activity/pi.py`
- Test: `backend/lumbergh/tests/test_pi_adapter.py`

**Interfaces:**
- `PiAdapter(AgentAdapter)` with `__init__(transcript_path, root=None)`, `for_cwd(cwd) -> PiAdapter | None`, `resolve(session_name, cwd) -> PiAdapter | None` (= `for_cwd`; Pi has no identity hook yet), `read_new()`, `_source_signature()` — same contract as `ClaudeCodeAdapter`.
- Sessions dir `~/.pi/agent/sessions/`; cwd encoding `"-" + str(cwd).replace("/", "-") + "--"`.

**Notes:** Pi lines are `{"type":"message","timestamp",...,"message":{"role":"user"|"assistant"|"toolResult","content":[...]}}`. Blocks: `text`, `thinking`, `toolCall{name,arguments,id}`; `toolResult` messages carry `toolCallId`,`toolName`,`content:[{type:"text",text}]`. Reuse `_parse_ts`/`_stringify_content` from `claude_code`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_pi_adapter.py
import json

from lumbergh.activity.pi import PiAdapter

LINES = [
    {"type": "session", "id": "sid", "timestamp": "2026-07-27T03:48:38.487Z", "cwd": "/w"},
    {"type": "message", "timestamp": "2026-07-27T03:48:38.545Z",
     "message": {"role": "user", "content": [{"type": "text", "text": "build wordfreq"}]}},
    {"type": "message", "timestamp": "2026-07-27T03:48:40.000Z",
     "message": {"role": "assistant", "content": [
         {"type": "thinking", "thinking": "planning"},
         {"type": "text", "text": "On it."},
         {"type": "toolCall", "id": "call_1", "name": "bash", "arguments": {"command": "uv init"}}]}},
    {"type": "message", "timestamp": "2026-07-27T03:48:41.000Z",
     "message": {"role": "toolResult", "toolCallId": "call_1", "toolName": "bash",
                 "content": [{"type": "text", "text": "done"}]}},
]


def _write(tmp_path):
    d = tmp_path / "-w--"
    d.mkdir()
    f = d / "2026-07-27T03-48-38_sid.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in LINES) + "\n")
    return f


def test_pi_adapter_parses_events(tmp_path):
    adapter = PiAdapter(_write(tmp_path), root="/w")
    events = adapter.read_new()
    kinds = [(e.type, e.tool_name, (e.text or e.tool_summary)) for e in events]
    assert ("user_message", None, "build wordfreq") in kinds
    assert ("thinking", None, "planning") in kinds
    assert ("agent_message", None, "On it.") in kinds
    assert ("tool_call", "bash", "uv init") in kinds
    tr = [e for e in events if e.type == "tool_result"]
    assert tr and tr[0].tool_use_id == "call_1" and tr[0].text == "done"


def test_for_cwd_encoding(tmp_path, monkeypatch):
    monkeypatch.setattr(PiAdapter, "SESSIONS_DIR", tmp_path)
    d = tmp_path / "--home-jvogel--"
    d.mkdir()
    (d / "a.jsonl").write_text(json.dumps(LINES[0]) + "\n")
    assert PiAdapter.for_cwd("/home/jvogel") is not None
    assert PiAdapter.for_cwd("/nope") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_pi_adapter.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `activity/pi.py`**

```python
# backend/lumbergh/activity/pi.py
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
        candidates = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return cls(candidates[0], root=cwd) if candidates else None

    @classmethod
    def resolve(cls, session_name: str, cwd) -> "PiAdapter | None":
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
            return [ConversationEvent(
                type="tool_result", id=self._eid(), timestamp=ts,
                tool_use_id=message.get("toolCallId"), tool_name=message.get("toolName"),
                status="ok", text=_stringify_content(message.get("content")),
            )]
        return []

    def _blocks_to_events(self, content, ts, assistant: bool) -> list[ConversationEvent]:
        events: list[ConversationEvent] = []
        for block in content or []:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                events.append(ConversationEvent(
                    type="agent_message" if assistant else "user_message",
                    id=self._eid(), timestamp=ts, text=block.get("text", "")))
            elif btype == "thinking" and assistant:
                events.append(ConversationEvent(
                    type="thinking", id=self._eid(), timestamp=ts, text=block.get("thinking", "")))
            elif btype == "toolCall" and assistant:
                name = block.get("name", "")
                args = block.get("arguments") or {}
                events.append(ConversationEvent(
                    type="tool_call", id=self._eid(), timestamp=ts, tool_name=name,
                    tool_summary=_summarize_pi_tool(name, args),
                    tool_detail=json.dumps(args, indent=2), tool_use_id=block.get("id")))
        return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_pi_adapter.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Validate against a REAL Pi transcript**

Run:
```
cd backend && uv run python -c "
from lumbergh.activity.pi import PiAdapter
from pathlib import Path
import glob
f = sorted(glob.glob(str(Path.home()/'.pi/agent/sessions/*/*.jsonl')))[-1]
ev = PiAdapter(f).read_new()
print('events:', len(ev))
from collections import Counter
print(Counter(e.type for e in ev))
"
```
Expected: prints a non-zero event count and a mix of `user_message`/`agent_message`/`thinking`/`tool_call`/`tool_result`. (Sanity only — no assertion.)

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/activity/pi.py backend/lumbergh/tests/test_pi_adapter.py
git commit -m "feat(activity): Pi transcript adapter"
```

---

### Task 6: Adapter resolver

**Files:**
- Create: `backend/lumbergh/activity/resolve.py`
- Test: `backend/lumbergh/tests/test_resolve_adapter.py`

**Interfaces:** `resolve_adapter(session_name: str, cwd: Path | None, provider: str | None) -> AgentAdapter | None` — pick by `provider` (`"pi"`→`PiAdapter`, else `ClaudeCodeAdapter`); if the chosen one returns None, try the other; None if neither resolves.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_resolve_adapter.py
import lumbergh.activity.resolve as r
from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.activity.pi import PiAdapter


def test_provider_pi_prefers_pi(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda cls, n, c: "PI"))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda cls, n, c: "CLAUDE"))
    assert r.resolve_adapter("s", "/w", "pi") == "PI"


def test_provider_claude_prefers_claude(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda cls, n, c: "PI"))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda cls, n, c: "CLAUDE"))
    assert r.resolve_adapter("s", "/w", "claude") == "CLAUDE"


def test_falls_back_to_other(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda cls, n, c: None))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda cls, n, c: "CLAUDE"))
    assert r.resolve_adapter("s", "/w", "pi") == "CLAUDE"


def test_none_when_neither(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda cls, n, c: None))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda cls, n, c: None))
    assert r.resolve_adapter("s", "/w", "claude") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_resolve_adapter.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `activity/resolve.py`**

```python
# backend/lumbergh/activity/resolve.py
"""Pick the transcript adapter for a session by its agent provider."""

from pathlib import Path

from lumbergh.activity.adapter import AgentAdapter
from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.activity.pi import PiAdapter


def resolve_adapter(session_name: str, cwd: Path | None, provider: str | None) -> AgentAdapter | None:
    order = [PiAdapter, ClaudeCodeAdapter] if (provider or "").lower() == "pi" else [
        ClaudeCodeAdapter, PiAdapter]
    for cls in order:
        adapter = cls.resolve(session_name, cwd)
        if adapter is not None:
            return adapter
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_resolve_adapter.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/activity/resolve.py backend/lumbergh/tests/test_resolve_adapter.py
git commit -m "feat(activity): provider-based adapter resolver"
```

---

### Task 7: `/api/agent` router

**Files:**
- Create: `backend/lumbergh/routers/agent.py`
- Modify: `backend/lumbergh/main.py` (include router; `ensure_token()` on startup)
- Test: `backend/lumbergh/tests/test_agent_router.py`

**Interfaces (all under `/api/agent`, JSON responses; CLI renders TOON):**
- `GET /sessions` → `{sessions:[{name,state,unseen}], total}`.
- `GET /sessions/{name}/read?source=transcript|pane|detection&last=10&full=false` →
  transcript: `{source, events:[{type,tool,text}], total}`; pane/detection: `{source, pane, note?}`.
- `GET /sessions/{name}/state` → `{session,state,unseen,since}`.
- `GET /sessions/{name}/wait?until=&timeout=300` → `{session,state,waited,reached}`.
- `POST /sessions/{name}/prompt` body `{text, wait=false}` → `{session,sent,state,changed}`.
- Unknown session → 404 `{error, sessions:[name,...]}`.

**Notes:** live sessions/state from `idle_monitor` + `session_attention` + `get_stored_sessions()`; cwd/provider from stored meta (`workdir`, `agent_provider`); transcript via `resolve_adapter`; pane via `capture_pane_text`; detection via `regions.extract("recent", capture_pane_text(name), "")`; prompt via `send_text`. Truncate text at 500 (transcript events) / 1500 (pane) unless `full`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_agent_router.py
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import lumbergh.routers.agent as agent
from lumbergh.idle_detector import SessionState


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(agent, "_live_names", lambda: ["s1"])
    monkeypatch.setattr(agent, "_meta", lambda n: {"workdir": "/w", "agent_provider": "pi"})
    monkeypatch.setattr(agent.idle_monitor, "get_state", lambda n: SessionState.BLOCKED)
    monkeypatch.setattr(agent.idle_monitor, "state_since_seconds", lambda n: 12.0)
    monkeypatch.setattr(agent.session_attention, "is_unseen", lambda n: True)
    app = FastAPI()
    app.include_router(agent.router)
    return TestClient(app)


def test_sessions_list(client):
    r = client.get("/api/agent/sessions").json()
    assert r["total"] == 1 and r["sessions"][0]["name"] == "s1"
    assert r["sessions"][0]["state"] == "blocked"


def test_state(client):
    r = client.get("/api/agent/sessions/s1/state").json()
    assert r["state"] == "blocked" and r["unseen"] is True and r["since"] == 12.0


def test_unknown_session_404(client):
    r = client.get("/api/agent/sessions/nope/state")
    assert r.status_code == 404 and "s1" in r.json()["sessions"]


def test_wait_returns_immediately_when_already_in_state(client):
    r = client.get("/api/agent/sessions/s1/wait?until=blocked&timeout=1").json()
    assert r["reached"] is True and r["state"] == "blocked"


def test_read_pane(client, monkeypatch):
    monkeypatch.setattr(agent, "capture_pane_text", lambda n, lines=None: "hello\nworld")
    r = client.get("/api/agent/sessions/s1/read?source=pane").json()
    assert r["source"] == "pane" and "hello" in r["pane"]


def test_prompt_sends(client, monkeypatch):
    sent = {}
    monkeypatch.setattr(agent, "send_text", lambda n, t: sent.update({n: t}) or True)
    r = client.post("/api/agent/sessions/s1/prompt", json={"text": "go"}).json()
    assert r["sent"] == "go" and sent["s1"] == "go"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_router.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `routers/agent.py`**

```python
# backend/lumbergh/routers/agent.py
"""Localhost, token-gated control surface for the `lb` agent CLI.

Serves live state from the in-memory monitor (no DB race), transcript content via
the activity adapters, and pane/send via tmux. Auth is enforced by AuthMiddleware
(the agent token); this router assumes an already-authorized request.
"""

import asyncio
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lumbergh import session_attention
from lumbergh.activity import regions
from lumbergh.activity.resolve import resolve_adapter
from lumbergh.idle_monitor import idle_monitor
from lumbergh.tmux_pty import capture_pane_text, send_text

router = APIRouter(prefix="/api/agent")

_REST = {"idle", "blocked", "error"}


def _live_names() -> list[str]:
    from lumbergh.routers.sessions import get_live_sessions

    return list(get_live_sessions().keys())


def _meta(name: str) -> dict:
    from lumbergh.routers.sessions import get_stored_sessions

    return get_stored_sessions().get(name, {})


def _require(name: str) -> None:
    if name not in _live_names():
        raise HTTPException(status_code=404, detail={"error": f'no session named "{name}"', "sessions": _live_names()})


def _state(name: str) -> str:
    return idle_monitor.get_state(name).value


@router.get("/sessions")
def sessions():
    names = _live_names()
    return {
        "total": len(names),
        "sessions": [
            {"name": n, "state": _state(n), "unseen": session_attention.is_unseen(n)} for n in names
        ],
    }


@router.get("/sessions/{name}/state")
def state(name: str):
    _require(name)
    return {
        "session": name,
        "state": _state(name),
        "unseen": session_attention.is_unseen(name),
        "since": idle_monitor.state_since_seconds(name),
    }


@router.get("/sessions/{name}/read")
def read(name: str, source: str = "transcript", last: int = 10, full: bool = False):
    _require(name)
    if source == "transcript":
        meta = _meta(name)
        cwd = Path(meta["workdir"]) if meta.get("workdir") else None
        adapter = resolve_adapter(name, cwd, meta.get("agent_provider"))
        if adapter is not None:
            events = adapter.read_new()
            recent = events[-last:]
            limit = None if full else 500
            return {
                "source": "transcript",
                "total": len(events),
                "events": [
                    {
                        "type": e.type,
                        "tool": e.tool_name or "",
                        "text": _trunc(e.text or e.tool_summary or "", limit),
                    }
                    for e in recent
                ],
            }
        # no transcript — fall through to pane with a note
        text = capture_pane_text(name)
        return {"source": "pane", "pane": _trunc(text, None if full else 1500),
                "note": "no transcript for this session; showing the pane"}
    if source == "detection":
        text = "\n".join(regions.extract("recent", capture_pane_text(name), ""))
        return {"source": "detection", "pane": text}
    text = capture_pane_text(name)
    return {"source": "pane", "pane": _trunc(text, None if full else 1500)}


@router.get("/sessions/{name}/wait")
async def wait(name: str, until: str, timeout: float = 300.0):
    _require(name)
    targets = _REST if until == "rest" else {until}
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    while True:
        st = _state(name)
        if st in targets:
            return {"session": name, "state": st, "waited": round(time.monotonic() - start, 1), "reached": True}
        if time.monotonic() >= deadline:
            return {"session": name, "state": st, "waited": round(time.monotonic() - start, 1), "reached": False}
        await asyncio.sleep(0.25)


class PromptBody(BaseModel):
    text: str
    wait: bool = False


@router.post("/sessions/{name}/prompt")
async def prompt(name: str, body: PromptBody):
    _require(name)
    before = _state(name)
    ok = send_text(name, body.text)
    if not ok:
        raise HTTPException(status_code=500, detail={"error": f"failed to send to {name}"})
    changed = False
    if body.wait:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if _state(name) != before:
                changed = True
                break
            await asyncio.sleep(0.25)
    return {"session": name, "sent": body.text, "state": _state(name), "changed": changed}


def _trunc(text: str, limit: int | None) -> str:
    if limit is None or len(text) <= limit:
        return text
    return text[:limit] + f"… ({len(text)} chars total)"
```

- [ ] **Step 4: Wire into `main.py`**

Add to the router imports (`from lumbergh.routers import ...`): `agent`. Add `app.include_router(agent.router)` with the others. In `lifespan`, next to `install_session_hook()`, add:

```python
    from lumbergh import agent_token

    agent_token.ensure_token()
```

- [ ] **Step 5: Run tests + import sanity**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_router.py -q && uv run python -c "import lumbergh.main"`
Expected: PASS (6 passed), import OK.

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/routers/agent.py backend/lumbergh/main.py backend/lumbergh/tests/test_agent_router.py
git commit -m "feat(agent): /api/agent control surface + startup token"
```

---

### Task 8: TOON renderer

**Files:**
- Create: `backend/lumbergh/agent_cli/__init__.py` (empty)
- Create: `backend/lumbergh/agent_cli/toon.py`
- Test: `backend/lumbergh/tests/test_toon.py`

**Interfaces:**
- `render_collection(name: str, rows: list[dict], fields: list[str]) -> str` — `name[count]{fields}:` + comma-delimited rows (values quoted when they contain space/comma/colon/quote or are empty).
- `render_object(pairs: list[tuple[str, object]]) -> str` — `key: value` lines (same quoting).
- `render_block(key: str, text: str) -> str` — `key: |` then indented lines.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_toon.py
from lumbergh.agent_cli.toon import render_block, render_collection, render_object


def test_collection():
    out = render_collection("sessions", [{"name": "a", "state": "idle"}], ["name", "state"])
    assert out.splitlines()[0] == "sessions[1]{name,state}:"
    assert out.splitlines()[1] == "  a,idle"


def test_collection_quotes_when_needed():
    out = render_collection("x", [{"t": "hi, there"}], ["t"])
    assert out.splitlines()[1] == '  "hi, there"'


def test_empty_collection():
    assert render_collection("x", [], ["a"]) == "x[0]{a}:"


def test_object():
    assert render_object([("state", "blocked"), ("since", 12)]) == "state: blocked\nsince: 12"


def test_block():
    out = render_block("pane", "l1\nl2")
    assert out == "pane: |\n  l1\n  l2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_toon.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `agent_cli/toon.py`**

```python
# backend/lumbergh/agent_cli/toon.py
"""Minimal TOON renderer for lb's stdout (applied only at the output boundary)."""


def _cell(value) -> str:
    if value is None:
        value = ""
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value)
    if s == "" or any(c in s for c in ' ,:"\n'):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def render_collection(name: str, rows: list[dict], fields: list[str]) -> str:
    header = f"{name}[{len(rows)}]{{{','.join(fields)}}}:"
    lines = [header]
    for row in rows:
        lines.append("  " + ",".join(_cell(row.get(f)) for f in fields))
    return "\n".join(lines)


def render_object(pairs) -> str:
    return "\n".join(f"{k}: {_cell(v)}" for k, v in pairs)


def render_block(key: str, text: str) -> str:
    body = "\n".join("  " + line for line in text.split("\n"))
    return f"{key}: |\n{body}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_toon.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/agent_cli/__init__.py backend/lumbergh/agent_cli/toon.py backend/lumbergh/tests/test_toon.py
git commit -m "feat(lb): TOON output renderer"
```

---

### Task 9: The `lb` CLI

**Files:**
- Create: `backend/lumbergh/agent_cli/main.py`
- Modify: `backend/pyproject.toml` (`[project.scripts] lb = "lumbergh.agent_cli.main:main"`)
- Test: `backend/lumbergh/tests/test_lb_cli.py`

**Interfaces:** `main(argv: list[str] | None = None) -> int` — parses argv, calls the backend, prints TOON to stdout, returns the exit code. Base URL from `LUMBERGH_URL` (default `http://127.0.0.1:8420`); token from `agent_token.read_token()`.

**Notes:** commands `""` (home) / `read` / `state` / `wait` / `prompt`. Per-command known-flag validation → exit 2 on unknown. Connection error → "server not running" exit 1. HTTP 404 → session error exit 1. Uses `httpx` (already a dep via version_check).

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_lb_cli.py
import httpx

import lumbergh.agent_cli.main as cli


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data


def _run(monkeypatch, argv, responder):
    monkeypatch.setattr(cli, "_request", responder)
    monkeypatch.setattr(cli.agent_token, "read_token", lambda: "tok")
    out = []
    monkeypatch.setattr(cli, "_emit", lambda s: out.append(s))
    code = cli.main(argv)
    return code, "\n".join(out)


def test_home_lists_sessions(monkeypatch):
    code, out = _run(monkeypatch, [],
        lambda m, p, **k: _Resp({"total": 1, "sessions": [{"name": "a", "state": "idle", "unseen": False}]}))
    assert code == 0
    assert "sessions[1]{name,state,unseen}:" in out
    assert "bin:" in out and "description:" in out


def test_unknown_flag_exit_2(monkeypatch):
    code, out = _run(monkeypatch, ["state", "--bogus"], lambda *a, **k: _Resp({}))
    assert code == 2 and "unknown flag --bogus" in out


def test_server_down_exit_1(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")
    code, out = _run(monkeypatch, [], boom)
    assert code == 1 and "server is not running" in out


def test_wait_timeout_exit_1(monkeypatch):
    code, out = _run(monkeypatch, ["wait", "--session", "s", "--until", "idle"],
        lambda m, p, **k: _Resp({"session": "s", "state": "working", "waited": 300, "reached": False}))
    assert code == 1 and "timed out" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_cli.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `agent_cli/main.py`**

```python
# backend/lumbergh/agent_cli/main.py
"""`lb` — agent-facing control CLI for Lumbergh (AXI). Prints TOON to stdout.

Provenance: control-API surface adapted in spirit from herdr (see
~/.config/lumbergh/shared/herdr-steal-list.md); no code copied. Built to the AXI
standard (`.claude/skills/axi`).
"""

import os
import sys
from pathlib import Path

import httpx

from lumbergh import agent_token
from lumbergh.agent_cli.toon import render_block, render_collection, render_object

BASE = os.environ.get("LUMBERGH_URL", "http://127.0.0.1:8420")
DESCRIPTION = "Observe and coordinate Lumbergh agent sessions from the shell"

FLAGS = {
    "": set(),
    "read": {"--session", "--source", "--last", "--full"},
    "state": {"--session"},
    "wait": {"--session", "--until", "--timeout"},
    "prompt": {"--session", "--wait"},
}


def _emit(s: str) -> None:
    print(s)


def _err(msg: str, help_line: str | None, code: int) -> int:
    _emit(f"error: {msg}")
    if help_line:
        _emit(f"help: {help_line}")
    return code


def _request(method: str, path: str, **kwargs):
    headers = {"X-Lumbergh-Agent-Token": agent_token.read_token() or ""}
    return httpx.request(method, f"{BASE}{path}", headers=headers, timeout=kwargs.pop("timeout", 320), **kwargs)


def _bin() -> str:
    return str(Path(sys.argv[0]).resolve()).replace(str(Path.home()), "~")


def _parse(argv):
    command = argv[0] if argv and not argv[0].startswith("-") else ""
    rest = argv[1:] if command else argv
    flags, positional = {}, []
    i = 0
    known = FLAGS.get(command)
    if known is None:
        return None, None, None, f"unknown command `{command}`"
    while i < len(rest):
        a = rest[i]
        if a == "--help":
            flags["--help"] = True
            i += 1
        elif a.startswith("--"):
            if a not in known:
                return command, None, None, f"unknown flag {a} for `{command or 'lb'}`"
            if a in ("--full", "--wait"):
                flags[a] = True
                i += 1
            else:
                flags[a] = rest[i + 1] if i + 1 < len(rest) else ""
                i += 2
        else:
            positional.append(a)
            i += 1
    return command, flags, positional, None


def _target(flags):
    return flags.get("--session") or os.environ.get("LUMBERGH_SESSION")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command, flags, positional, perr = _parse(argv)
    if perr:
        valid = " ".join(sorted(FLAGS.get(command, []))) or "(none)"
        return _err(perr, f"valid flags for `{command or 'lb'}`: {valid} (--help always allowed)", 2)

    try:
        if command == "":
            return _cmd_home()
        if command == "state":
            return _cmd_state(_target(flags))
        if command == "read":
            return _cmd_read(_target(flags), flags)
        if command == "wait":
            return _cmd_wait(_target(flags), flags)
        if command == "prompt":
            return _cmd_prompt(_target(flags), positional, flags)
    except httpx.ConnectError:
        return _err("Lumbergh server is not running", "start it with `lumbergh`, then retry", 1)
    return _err(f"unknown command `{command}`", "run `lb` for the home view", 2)


def _need_session(session) -> int | None:
    if not session:
        return _err("no session given", "pass --session <name> or set $LUMBERGH_SESSION", 2)
    return None


def _session_404(resp) -> int:
    detail = resp.json().get("detail", {})
    _emit(f"error: {detail.get('error', 'unknown session')}")
    _emit(render_collection("sessions", [{"name": n} for n in detail.get("sessions", [])], ["name"]))
    _emit("help: run `lb` to list sessions")
    return 1


def _cmd_home() -> int:
    data = _request("GET", "/api/agent/sessions").json()
    _emit(render_object([("bin", _bin()), ("description", DESCRIPTION),
                         ("count", f"{data['total']} of {data['total']} total")]))
    if data["total"] == 0:
        _emit("sessions: 0 live sessions")
        return 0
    _emit(render_collection("sessions", data["sessions"], ["name", "state", "unseen"]))
    _emit(render_collection("help", [
        {"h": "Run `lb read --session <name>` to see a session"},
        {"h": "Run `lb wait --session <name> --until idle` to block until it finishes"},
    ], ["h"]).replace("help[2]{h}:\n", "help[2]:\n"))
    return 0


def _cmd_state(session) -> int:
    if (e := _need_session(session)) is not None:
        return e
    resp = _request("GET", f"/api/agent/sessions/{session}/state")
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    _emit(render_object([("session", d["session"]), ("state", d["state"]),
                         ("unseen", d["unseen"]), ("since", f"{round(d['since'])}s" if d.get("since") else "")]))
    return 0


def _cmd_read(session, flags) -> int:
    if (e := _need_session(session)) is not None:
        return e
    params = {"source": flags.get("--source", "transcript"),
              "last": flags.get("--last", "10"), "full": str("--full" in flags).lower()}
    resp = _request("GET", f"/api/agent/sessions/{session}/read", params=params)
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    if d["source"] == "transcript":
        _emit(render_object([("session", session), ("source", "transcript"),
                             ("count", f"{len(d['events'])} of {d['total']} events")]))
        _emit(render_collection("events", d["events"], ["type", "tool", "text"]))
    else:
        pairs = [("session", session), ("source", d["source"])]
        if d.get("note"):
            pairs.append(("note", d["note"]))
        _emit(render_object(pairs))
        _emit(render_block("pane", d.get("pane", "")))
    return 0


def _cmd_wait(session, flags) -> int:
    if (e := _need_session(session)) is not None:
        return e
    until = flags.get("--until")
    if not until:
        return _err("--until is required", "lb wait --until idle|working|blocked|error|rest [--timeout <s>]", 2)
    timeout = flags.get("--timeout", "300")
    resp = _request("GET", f"/api/agent/sessions/{session}/wait",
                    params={"until": until, "timeout": timeout})
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    if not d["reached"]:
        return _err(f"timed out after {timeout}s waiting for {session} to reach `{until}` (still `{d['state']}`)",
                    f"raise --timeout or check `lb read --session {session}`", 1)
    _emit(render_object([("session", session), ("state", d["state"]), ("waited", f"{d['waited']}s")]))
    return 0


def _cmd_prompt(session, positional, flags) -> int:
    if (e := _need_session(session)) is not None:
        return e
    if not positional:
        return _err("prompt text is required", 'lb prompt "<text>" [--wait] [--session <name>]', 2)
    body = {"text": positional[0], "wait": "--wait" in flags}
    resp = _request("POST", f"/api/agent/sessions/{session}/prompt", json=body)
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    _emit(render_object([("session", session), ("sent", d["sent"]), ("state", d["state"])]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

(Note: the `help[2]` hint in `_cmd_home` is rendered via `render_collection` then relabelled — if that reads awkwardly during implementation, emit the two `help` lines directly with a small helper instead; the test only checks the `sessions[..]` header.)

- [ ] **Step 4: Add the console script**

In `backend/pyproject.toml` under `[project.scripts]` (next to `lumbergh = ...`):

```toml
lb = "lumbergh.agent_cli.main:main"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_cli.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/agent_cli/main.py backend/pyproject.toml backend/lumbergh/tests/test_lb_cli.py
git commit -m "feat(lb): agent control CLI entry point"
```

---

### Task 10: Full verification + live smoke

- [ ] **Step 1: Full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: all PASS (prior suites + the ~30 new agent/CLI/adapter tests).

- [ ] **Step 2: Lint**

Run: `./lint.sh`
Expected: exits 0. Fix any new errors and re-run.

- [ ] **Step 3: Live smoke against a real Pi session**

With the Lumbergh server running (`./backend/start.sh` or the running instance) and Pi available:
1. Create a scratch tmux session running Pi (or use an existing Lumbergh Pi session).
2. Run:
   ```
   cd backend && uv run lb            # home view — should list sessions in TOON
   uv run lb read --session <pi-session>          # transcript events from PiAdapter
   uv run lb state --session <pi-session>
   ```
Expected: `lb` prints TOON with the live sessions; `lb read` shows Pi conversation events (user_message/agent_message/tool_call/tool_result), proving the PiAdapter works end-to-end. Capture the output in the task notes. (Best-effort: if the server isn't running in this environment, note it and rely on the unit suite.)

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "chore(lb): verification fixups"
```

(Skip if nothing changed. Never sweep `.agents/`, `.claude/skills/`, `skills-lock.json`, or `frontend/package-lock.json`.)

---

## Self-Review

**Spec coverage:** token (T1) + auth exemption (T2); `state`/`wait` from in-memory monitor incl. time-in-state (T3, T7); clean pane + send (T4); transcript-first `read` via `ClaudeCodeAdapter` + new `PiAdapter` (T5) selected by provider (T6); the five commands over `/api/agent` (T7) rendered as TOON (T8) by `lb` with AXI errors/exit codes/flag validation (T9); live Pi smoke (T10). #5 hand-off and v2 primitives remain out of scope. ✓

**Placeholder scan:** No TBD/TODO; every code step is complete; the one `_cmd_home` rendering nuance is flagged with a concrete fallback. ✓

**Type consistency:** `ConversationEvent` fields used by `PiAdapter` (T5) match the model and how the router serializes them (T7: `type`/`tool_name`/`text`/`tool_summary`); `resolve_adapter(name,cwd,provider)` (T6) called with `(name, Path|None, provider)` in T7; `agent_token.read_token/verify` (T1) used by T2 and T9; TOON `render_*` signatures (T8) match CLI calls (T9); `capture_pane_text`/`send_text` (T4) used in T7. ✓
```
