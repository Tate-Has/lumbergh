# SessionStart Hook for Transcript Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Lumbergh authoritative Claude Code transcript identity (`session_id` + `transcript_path`) per session via a `SessionStart` hook, replacing the fragile newest-mtime cwd guess.

**Architecture:** A shipped, self-contained Python hook writes a per-session identity file to `~/.config/lumbergh/session_identity/`. The backend idempotently installs the hook into `~/.claude/settings.json` on startup (env-gated silent no-op elsewhere), injects `LUMBERGH_SESSION` into each pane it launches, and resolves the activity adapter identity-first with a graceful fall back to the legacy cwd guess.

**Tech Stack:** Python 3.11+ (stdlib `json`/`tomllib` not needed here), FastAPI lifespan, tmux/libtmux subprocess, pytest.

## Global Constraints

- Python **3.11+**; no new dependencies.
- The hook script is **self-contained stdlib only** — it must NOT import the `lumbergh` package.
- The hook and installer must be **best-effort**: never block/degrade a Claude session; never overwrite a `settings.json` that cannot be parsed.
- Config base dir is `CONFIG_DIR` from `lumbergh/constants.py` = `os.environ.get("LUMBERGH_DATA_DIR", ~/.config/lumbergh)`. The hook replicates this resolution exactly (it can't import it).
- `settings.json` hook shape is `{"hooks": {"SessionStart": [ {"hooks": [ {"type": "command", "command": "..."} ]} ]}}` (array of matcher-groups). Preserve all existing hooks.
- Managed-entry detection is by the substring `lumbergh_session_start.py` in a SessionStart command (move-proof across reinstalls).
- Run `./lint.sh` clean before completion.
- Commit messages: no AI attribution / Co-Authored-By lines.

---

### Task 1: Identity file-drop store

**Files:**
- Modify: `backend/lumbergh/constants.py` (add `SESSION_IDENTITY_DIR`)
- Create: `backend/lumbergh/session_identity.py`
- Test: `backend/lumbergh/tests/test_session_identity.py`

**Interfaces:**
- Produces:
  - `SESSION_IDENTITY_DIR: Path` in constants (`CONFIG_DIR / "session_identity"`).
  - `Identity` dataclass: `session_id: str`, `transcript_path: str`, `cwd: str`, `source: str`, `written_at: float`.
  - `key(name: str) -> str` — filename-safe key (non-`[A-Za-z0-9_-]` → `_`).
  - `store_dir() -> Path` — returns `SESSION_IDENTITY_DIR`.
  - `write(name: str, identity: Identity, store: Path | None = None) -> None`.
  - `read(name: str, store: Path | None = None) -> Identity | None` — None on missing/malformed.
  - `prune(live_names: set[str], store: Path | None = None) -> None` — delete files whose key is not for a live name.

- [ ] **Step 1: Add the constant**

In `backend/lumbergh/constants.py`, after `SESSIONS_DATA_DIR`:

```python
SESSION_IDENTITY_DIR = CONFIG_DIR / "session_identity"
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/lumbergh/tests/test_session_identity.py
from lumbergh.session_identity import Identity, key, prune, read, write


def _ident(**kw):
    base = dict(
        session_id="s1", transcript_path="/t/x.jsonl", cwd="/work", source="startup", written_at=1.0
    )
    base.update(kw)
    return Identity(**base)


def test_write_then_read_round_trip(tmp_path):
    write("my-sess", _ident(), store=tmp_path)
    got = read("my-sess", store=tmp_path)
    assert got is not None
    assert got.session_id == "s1"
    assert got.transcript_path == "/t/x.jsonl"
    assert got.source == "startup"


def test_read_missing_returns_none(tmp_path):
    assert read("nope", store=tmp_path) is None


def test_read_malformed_returns_none(tmp_path):
    (tmp_path / f"{key('bad')}.json").write_text("{not json")
    assert read("bad", store=tmp_path) is None


def test_key_is_filename_safe():
    assert key("a/b c:d") == "a_b_c_d"
    assert key("plain-name_1") == "plain-name_1"


def test_prune_removes_only_dead_sessions(tmp_path):
    write("alive", _ident(), store=tmp_path)
    write("dead", _ident(), store=tmp_path)
    prune({"alive"}, store=tmp_path)
    assert read("alive", store=tmp_path) is not None
    assert read("dead", store=tmp_path) is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_identity.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.session_identity'`

- [ ] **Step 4: Implement `session_identity.py`**

```python
# backend/lumbergh/session_identity.py
"""Per-session Claude transcript identity, written by the SessionStart hook.

The hook (backend/lumbergh/hooks/lumbergh_session_start.py) writes these files;
the backend reads them to locate a session's transcript authoritatively instead
of guessing from the cwd. Keep key()/paths in lockstep with the hook — the
hook is self-contained and cannot import this module, so a round-trip test pins
the contract.
"""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from lumbergh.constants import SESSION_IDENTITY_DIR


@dataclass
class Identity:
    session_id: str
    transcript_path: str
    cwd: str
    source: str
    written_at: float


def key(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def store_dir() -> Path:
    return SESSION_IDENTITY_DIR


def _path(name: str, store: Path | None) -> Path:
    return (store or store_dir()) / f"{key(name)}.json"


def write(name: str, identity: Identity, store: Path | None = None) -> None:
    target = _path(name, store)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(asdict(identity), f)
    os.replace(tmp, target)


def read(name: str, store: Path | None = None) -> Identity | None:
    try:
        data = json.loads(_path(name, store).read_text())
        return Identity(
            session_id=data.get("session_id", ""),
            transcript_path=data.get("transcript_path", ""),
            cwd=data.get("cwd", ""),
            source=data.get("source", ""),
            written_at=float(data.get("written_at", 0.0)),
        )
    except (OSError, ValueError):
        return None


def prune(live_names: set[str], store: Path | None = None) -> None:
    directory = store or store_dir()
    if not directory.is_dir():
        return
    live_keys = {key(n) for n in live_names}
    for path in directory.glob("*.json"):
        if path.stem not in live_keys:
            path.unlink(missing_ok=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_identity.py -q`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/constants.py backend/lumbergh/session_identity.py backend/lumbergh/tests/test_session_identity.py
git commit -m "feat(identity): per-session transcript identity file store"
```

---

### Task 2: The SessionStart hook script

**Files:**
- Create: `backend/lumbergh/hooks/lumbergh_session_start.py`
- Test: `backend/lumbergh/tests/test_session_start_hook.py`

**Interfaces:**
- Consumes: `session_identity.read` (Task 1) for the round-trip assertion.
- Produces: an executable-by-path Python script. With `LUMBERGH_SESSION` set, reads a SessionStart JSON payload on stdin and writes `<store>/<key>.json`; with it unset, writes nothing and exits 0. Honors `LUMBERGH_DATA_DIR` for the store base, exactly like `CONFIG_DIR`.

**Notes:** The script must not import `lumbergh`. Its `store_dir()`/`key()` mirror `session_identity`; the test pins that they agree by writing via the hook and reading via `session_identity.read`.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_session_start_hook.py
import json
import subprocess
import sys
from pathlib import Path

from lumbergh.session_identity import read

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "lumbergh_session_start.py"

PAYLOAD = {
    "session_id": "abc123",
    "transcript_path": "/home/u/.claude/projects/enc/abc123.jsonl",
    "cwd": "/home/u/proj",
    "source": "startup",
    "hook_event_name": "SessionStart",
}


def _run(env_extra, payload):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env_extra,
    )


def test_writes_identity_when_session_env_set(tmp_path):
    env = {"LUMBERGH_DATA_DIR": str(tmp_path), "LUMBERGH_SESSION": "my sess"}
    result = _run(env, PAYLOAD)
    assert result.returncode == 0
    assert result.stdout == ""
    ident = read("my sess", store=tmp_path / "session_identity")
    assert ident is not None
    assert ident.session_id == "abc123"
    assert ident.transcript_path == PAYLOAD["transcript_path"]
    assert ident.source == "startup"


def test_noop_when_session_env_absent(tmp_path):
    env = {"LUMBERGH_DATA_DIR": str(tmp_path)}
    result = _run(env, PAYLOAD)
    assert result.returncode == 0
    assert not (tmp_path / "session_identity").exists()


def test_noop_on_malformed_stdin(tmp_path):
    env = {"LUMBERGH_DATA_DIR": str(tmp_path), "LUMBERGH_SESSION": "s"}
    result = subprocess.run(
        [sys.executable, str(HOOK)], input="{not json", capture_output=True, text=True, env=env
    )
    assert result.returncode == 0
    assert read("s", store=tmp_path / "session_identity") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_start_hook.py -q`
Expected: FAIL — the hook file does not exist (`can't open file .../lumbergh_session_start.py`), so subprocess returns non-zero / the read assertions fail.

- [ ] **Step 3: Implement the hook**

```python
# backend/lumbergh/hooks/lumbergh_session_start.py
"""Lumbergh SessionStart hook — reports Claude transcript identity to a file.

Self-contained (stdlib only): it must NOT import the lumbergh package, so no
unrelated import error can degrade the Claude session it runs inside. Best-effort
throughout — any problem exits 0 with no output. Silent no-op unless
LUMBERGH_SESSION is set (only Lumbergh-launched panes set it), which is what makes
a global install in ~/.claude/settings.json harmless everywhere else.

Store path + key mirror lumbergh.session_identity; a round-trip test pins them.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path


def _store_dir() -> Path:
    base = os.environ.get("LUMBERGH_DATA_DIR")
    root = Path(base) if base else Path.home() / ".config" / "lumbergh"
    return root / "session_identity"


def _key(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def main() -> int:
    session = os.environ.get("LUMBERGH_SESSION")
    if not session:
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    record = {
        "session_id": data.get("session_id", ""),
        "transcript_path": data.get("transcript_path", ""),
        "cwd": data.get("cwd", ""),
        "source": data.get("source", ""),
        "written_at": time.time(),
    }
    try:
        directory = _store_dir()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{_key(session)}.json"
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(record, f)
        os.replace(tmp, target)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_start_hook.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/hooks/lumbergh_session_start.py backend/lumbergh/tests/test_session_start_hook.py
git commit -m "feat(identity): self-contained SessionStart hook script"
```

---

### Task 3: Idempotent settings.json installer

**Files:**
- Create: `backend/lumbergh/hook_installer.py`
- Test: `backend/lumbergh/tests/test_hook_installer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (paths are injected for testability).
- Produces:
  - `hook_script_path() -> Path` — absolute path to `hooks/lumbergh_session_start.py`.
  - `default_settings_path() -> Path` — `~/.claude/settings.json`.
  - `desired_command(interpreter: str, script: Path) -> str` — `shlex.quote`d `"<interpreter> <script>"`.
  - `ensure_installed(settings_path: Path | None = None, interpreter: str | None = None, script: Path | None = None) -> bool` — install/update the managed SessionStart entry idempotently; return True if the settings now contain the correct entry, False if skipped (unparseable settings).
  - `uninstall(settings_path: Path | None = None) -> bool` — remove only the managed entry.

**Notes:** Managed entry = a SessionStart matcher-group whose inner command contains `lumbergh_session_start.py`. Idempotent = if the desired command already matches, write nothing.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_hook_installer.py
import json

from lumbergh.hook_installer import desired_command, ensure_installed, uninstall

MARKER = "lumbergh_session_start.py"


def _settings(tmp_path):
    return tmp_path / "settings.json"


def _managed_groups(path):
    hooks = json.loads(path.read_text()).get("hooks", {}).get("SessionStart", [])
    return [g for g in hooks if any(MARKER in h.get("command", "") for h in g.get("hooks", []))]


def test_fresh_install_creates_managed_entry(tmp_path):
    sp = _settings(tmp_path)
    assert ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER) is True
    groups = _managed_groups(sp)
    assert len(groups) == 1
    assert groups[0]["hooks"][0]["type"] == "command"


def test_idempotent_rerun_is_byte_identical(tmp_path):
    sp = _settings(tmp_path)
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    first = sp.read_text()
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    assert sp.read_text() == first
    assert len(_managed_groups(sp)) == 1


def test_preserves_unrelated_hooks(tmp_path):
    sp = _settings(tmp_path)
    sp.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": "~/x.sh"}]}]}}))
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    data = json.loads(sp.read_text())
    assert data["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
    assert len(_managed_groups(sp)) == 1


def test_stale_interpreter_is_rewritten(tmp_path):
    sp = _settings(tmp_path)
    ensure_installed(settings_path=sp, interpreter="/old/py", script=tmp_path / MARKER)
    ensure_installed(settings_path=sp, interpreter="/new/py", script=tmp_path / MARKER)
    groups = _managed_groups(sp)
    assert len(groups) == 1
    assert groups[0]["hooks"][0]["command"] == desired_command("/new/py", tmp_path / MARKER)


def test_malformed_settings_left_untouched(tmp_path):
    sp = _settings(tmp_path)
    sp.write_text("{ this is not json")
    assert ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER) is False
    assert sp.read_text() == "{ this is not json"


def test_uninstall_removes_only_managed(tmp_path):
    sp = _settings(tmp_path)
    sp.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": "/other/hook.py"}]}]}}))
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    assert uninstall(settings_path=sp) is True
    hooks = json.loads(sp.read_text())["hooks"]["SessionStart"]
    assert len(hooks) == 1
    assert hooks[0]["hooks"][0]["command"] == "/other/hook.py"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_hook_installer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.hook_installer'`

- [ ] **Step 3: Implement `hook_installer.py`**

```python
# backend/lumbergh/hook_installer.py
"""Idempotent install of the Lumbergh SessionStart hook into ~/.claude/settings.json.

Env-gated silent no-op hook + versioned managed entry is a pattern adapted in
spirit from herdr (see ~/.config/lumbergh/shared/herdr-steal-list.md); no code
copied. The installer never overwrites a settings.json it cannot parse.
"""

import json
import logging
import os
import shlex
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_MARKER = "lumbergh_session_start.py"


def hook_script_path() -> Path:
    return Path(__file__).resolve().parent / "hooks" / _MARKER


def default_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def desired_command(interpreter: str, script: Path) -> str:
    return f"{shlex.quote(interpreter)} {shlex.quote(str(script))}"


def _is_managed(group: dict) -> bool:
    return any(_MARKER in h.get("command", "") for h in group.get("hooks", []))


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def ensure_installed(
    settings_path: Path | None = None,
    interpreter: str | None = None,
    script: Path | None = None,
) -> bool:
    settings_path = settings_path or default_settings_path()
    interpreter = interpreter or sys.executable
    script = script or hook_script_path()
    command = desired_command(interpreter, script)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except ValueError:
            logger.warning("settings.json is not valid JSON; leaving it untouched: %s", settings_path)
            return False
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])

    managed = next((g for g in session_start if _is_managed(g)), None)
    if managed is not None:
        if managed["hooks"][0].get("command") == command:
            return True  # already correct — write nothing
        managed["hooks"] = [{"type": "command", "command": command}]
    else:
        session_start.append({"hooks": [{"type": "command", "command": command}]})

    _atomic_write(settings_path, settings)
    return True


def uninstall(settings_path: Path | None = None) -> bool:
    settings_path = settings_path or default_settings_path()
    if not settings_path.exists():
        return True
    try:
        settings = json.loads(settings_path.read_text())
    except ValueError:
        return False
    session_start = settings.get("hooks", {}).get("SessionStart")
    if not session_start:
        return True
    kept = [g for g in session_start if not _is_managed(g)]
    settings["hooks"]["SessionStart"] = kept
    _atomic_write(settings_path, settings)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_hook_installer.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/hook_installer.py backend/lumbergh/tests/test_hook_installer.py
git commit -m "feat(identity): idempotent SessionStart hook installer"
```

---

### Task 4: Install on backend startup

**Files:**
- Modify: `backend/lumbergh/main.py` (call `ensure_installed` in `lifespan`)
- Test: `backend/lumbergh/tests/test_startup_hook_install.py`

**Interfaces:**
- Consumes: `hook_installer.ensure_installed` (Task 3).
- Produces: no new public API; startup best-effort-installs the hook.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_startup_hook_install.py
import lumbergh.hook_installer as hook_installer


def test_ensure_installed_survives_exceptions(monkeypatch):
    # Startup must never crash if hook install fails.
    def boom(*a, **k):
        raise RuntimeError("no home")

    monkeypatch.setattr(hook_installer, "ensure_installed", boom)
    from lumbergh.main import install_session_hook

    install_session_hook()  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_startup_hook_install.py -q`
Expected: FAIL — `ImportError: cannot import name 'install_session_hook'`

- [ ] **Step 3: Add a best-effort installer call in `main.py`**

Add a module-level helper (near the other startup helpers, above `lifespan`):

```python
def install_session_hook() -> None:
    """Best-effort install of the Claude SessionStart identity hook."""
    from lumbergh import hook_installer

    try:
        hook_installer.ensure_installed()
    except Exception as exc:  # noqa: BLE001 - startup must not fail on hook install
        logger.warning("Could not install SessionStart hook: %s", exc)
```

Then call it inside `lifespan`, right before `idle_monitor.start()` (line ~80):

```python
    install_session_hook()

    # Start background services
    idle_monitor.start()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_startup_hook_install.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/main.py backend/lumbergh/tests/test_startup_hook_install.py
git commit -m "feat(identity): install SessionStart hook on backend startup"
```

---

### Task 5: Inject LUMBERGH_SESSION at session creation

**Files:**
- Modify: `backend/lumbergh/routers/sessions.py` (`create_tmux_session`)
- Test: `backend/lumbergh/tests/test_session_env_injection.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `create_tmux_session` sends an `export LUMBERGH_SESSION=<name>` keystroke into the pane before the agent launch keystroke.

**Notes:** `create_tmux_session` is at `sessions.py:175`. It runs `tmux new-session`, an optional venv `source`, then the launch `send-keys`. Insert the export send-keys immediately after the successful `new-session`, before venv activation.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_session_env_injection.py
import subprocess
from pathlib import Path
from unittest.mock import patch

from lumbergh.routers.sessions import create_tmux_session


def test_injects_lumbergh_session_env(tmp_path: Path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("lumbergh.routers.sessions.subprocess.run", side_effect=fake_run):
        create_tmux_session("mysess", tmp_path, launch_command="claude")

    send_keys = [c for c in calls if "send-keys" in c]
    exports = [c for c in send_keys if any("export LUMBERGH_SESSION=" in str(a) for a in c)]
    assert exports, f"no export keystroke found in {send_keys}"
    assert any("mysess" in str(a) for a in exports[0])
    # The export must be sent before the launch command keystroke.
    launch_idx = next(i for i, c in enumerate(calls) if any("claude" in str(a) for a in c))
    export_idx = next(i for i, c in enumerate(calls) if any("export LUMBERGH_SESSION=" in str(a) for a in c))
    assert export_idx < launch_idx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_env_injection.py -q`
Expected: FAIL — no export keystroke found.

- [ ] **Step 3: Inject the env in `create_tmux_session`**

Add `import shlex` at the top of `sessions.py` if not present. After the `new-session` success check (right after the `if result.returncode != 0: raise ...` block, before the venv activation), insert:

```python
    # Correlate this pane to its Lumbergh session for the SessionStart hook.
    subprocess.run(
        [TMUX_CMD, "send-keys", "-t", name, f"export LUMBERGH_SESSION={shlex.quote(name)}", "Enter"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_env_injection.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/sessions.py backend/lumbergh/tests/test_session_env_injection.py
git commit -m "feat(identity): inject LUMBERGH_SESSION into launched panes"
```

---

### Task 6: Identity-first adapter resolution

**Files:**
- Modify: `backend/lumbergh/activity/claude_code.py` (add `ClaudeCodeAdapter.resolve`)
- Modify: `backend/lumbergh/main.py` (activity socket uses `resolve`)
- Test: `backend/lumbergh/tests/test_adapter_resolve.py`

**Interfaces:**
- Consumes: `session_identity.read` (Task 1); existing `ClaudeCodeAdapter.__init__(transcript_path, root)` and `for_cwd` (`claude_code.py:95,100`).
- Produces: `ClaudeCodeAdapter.resolve(session_name: str, cwd: Path | None) -> ClaudeCodeAdapter | None` — identity first (only when its `transcript_path` exists on disk), else the legacy `for_cwd(cwd)`, else None.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_adapter_resolve.py
from pathlib import Path

import lumbergh.activity.claude_code as cc
from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.session_identity import Identity


def test_resolve_uses_identity_when_transcript_exists(tmp_path, monkeypatch):
    transcript = tmp_path / "abc.jsonl"
    transcript.write_text("")
    ident = Identity("s1", str(transcript), str(tmp_path), "startup", 1.0)
    monkeypatch.setattr(cc, "read_identity", lambda name: ident)
    adapter = ClaudeCodeAdapter.resolve("sess", tmp_path)
    assert adapter is not None
    assert adapter.path == transcript


def test_resolve_falls_back_when_transcript_missing(tmp_path, monkeypatch):
    ident = Identity("s1", str(tmp_path / "gone.jsonl"), str(tmp_path), "startup", 1.0)
    monkeypatch.setattr(cc, "read_identity", lambda name: ident)
    called = {}
    monkeypatch.setattr(ClaudeCodeAdapter, "for_cwd", classmethod(lambda cls, cwd: called.setdefault("cwd", cwd)))
    ClaudeCodeAdapter.resolve("sess", tmp_path)
    assert called["cwd"] == tmp_path


def test_resolve_falls_back_when_no_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "read_identity", lambda name: None)
    called = {}
    monkeypatch.setattr(ClaudeCodeAdapter, "for_cwd", classmethod(lambda cls, cwd: called.setdefault("cwd", cwd)))
    ClaudeCodeAdapter.resolve("sess", tmp_path)
    assert called["cwd"] == tmp_path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_adapter_resolve.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'read_identity'` / `resolve`.

- [ ] **Step 3: Add `resolve` to `ClaudeCodeAdapter`**

At the top of `backend/lumbergh/activity/claude_code.py`, add a module-level import alias (so tests can monkeypatch it):

```python
from lumbergh.session_identity import read as read_identity
```

Then add the classmethod just after `for_cwd` (after `claude_code.py:113`):

```python
    @classmethod
    def resolve(cls, session_name: str, cwd: Path | None) -> "ClaudeCodeAdapter | None":
        """Locate the transcript authoritatively (hook identity), else guess by cwd."""
        ident = read_identity(session_name)
        if ident and ident.transcript_path and Path(ident.transcript_path).exists():
            root = Path(ident.cwd) if ident.cwd else cwd
            return cls(Path(ident.transcript_path), root=root)
        if cwd is not None:
            return cls.for_cwd(cwd)
        return None
```

- [ ] **Step 4: Point the activity socket at `resolve`**

In `backend/lumbergh/main.py` (activity socket, ~line 537-538), replace:

```python
    cwd = await _session_cwd(session_name)
    adapter = ClaudeCodeAdapter.for_cwd(cwd) if cwd else None
```

with:

```python
    cwd = await _session_cwd(session_name)
    adapter = ClaudeCodeAdapter.resolve(session_name, cwd)
```

- [ ] **Step 5: Run tests + activity import sanity**

Run: `cd backend && uv run pytest lumbergh/tests/test_adapter_resolve.py -q && uv run python -c "import lumbergh.main"`
Expected: PASS (3 passed) and the import prints nothing / exits 0.

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/activity/claude_code.py backend/lumbergh/main.py backend/lumbergh/tests/test_adapter_resolve.py
git commit -m "feat(identity): resolve transcript from hook identity, fall back to cwd"
```

---

### Task 7: Prune identity files for dead sessions

**Files:**
- Modify: `backend/lumbergh/idle_monitor.py` (prune identity when a session disappears)
- Test: `backend/lumbergh/tests/test_identity_prune_on_death.py`

**Interfaces:**
- Consumes: `session_identity.prune` (Task 1).
- Produces: the monitor's dead-session cleanup also drops stale identity files.

**Notes:** `_check_all_sessions` computes `dead_sessions` and pops per-session dicts (`idle_monitor.py:143-148`). Add a prune of live names there. Import `session_identity` at module top.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_identity_prune_on_death.py
import lumbergh.idle_monitor as im


def test_check_all_sessions_prunes_identity(monkeypatch):
    monitor = im.IdleMonitor()
    monitor._fingerprints = {"dead": "x"}
    monkeypatch.setattr(monitor, "_get_live_session_names", lambda: ["alive"])
    pruned = {}
    monkeypatch.setattr(im.session_identity, "prune", lambda live: pruned.setdefault("live", set(live)))

    import asyncio

    async def _noop(name):
        return None

    monkeypatch.setattr(monitor, "_check_session", _noop)
    asyncio.get_event_loop().run_until_complete(monitor._check_all_sessions())
    assert pruned["live"] == {"alive"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_identity_prune_on_death.py -q`
Expected: FAIL — `AttributeError: module 'lumbergh.idle_monitor' has no attribute 'session_identity'`.

- [ ] **Step 3: Prune in `_check_all_sessions`**

Add the import near the other imports at the top of `idle_monitor.py`:

```python
from lumbergh import session_identity
```

In `_check_all_sessions`, after the `dead_sessions` cleanup loop and before the `asyncio.gather(...)`, add:

```python
        session_identity.prune(set(sessions))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_identity_prune_on_death.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/idle_monitor.py backend/lumbergh/tests/test_identity_prune_on_death.py
git commit -m "feat(identity): prune identity files when sessions end"
```

---

### Task 8: Packaging and full verification

**Files:**
- Verify (no edit expected): `backend/pyproject.toml` packages the hook script.

- [ ] **Step 1: Confirm the hook ships in the wheel**

Run:
```
cd backend && rm -rf dist && uv build --wheel 2>&1 | tail -1 && uv run python -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); print([n for n in z.namelist() if 'hooks' in n])"
```
Expected: the list includes `lumbergh/hooks/lumbergh_session_start.py`. (Hatchling includes package data by default, as verified for the detect manifests; if for any reason it is absent, add `[tool.hatch.build.targets.wheel.force-include]` mapping `lumbergh/hooks` and re-verify.) Then `rm -rf dist`.

- [ ] **Step 2: Full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: all PASS (prior suites + the 19 new tests across Tasks 1-7).

- [ ] **Step 3: Lint**

Run: `./lint.sh`
Expected: exits 0 (auto-fixes applied; fix any remaining errors and re-run).

- [ ] **Step 4: Commit any lint/packaging changes**

```bash
git add -A
git commit -m "chore(identity): package hook script and lint cleanups"
```

(If nothing changed, skip the commit.)

---

## Self-Review

**Spec coverage:**
- Hook script, self-contained stdlib, env-gated, writes identity file → Task 2. ✓
- Idempotent auto-install into settings.json, preserves other hooks, refuses malformed → Task 3; on startup best-effort → Task 4. ✓
- `LUMBERGH_SESSION` injection as correlation key → Task 5. ✓
- File-drop store (read/write/prune, Identity) → Task 1; prune on death → Task 7. ✓
- Adapter resolution identity-first with cwd fallback (only when transcript exists) → Task 6. ✓
- Interpreter baked from `sys.executable`, rewritten on drift → Task 3 (`ensure_installed` default + stale-interpreter test). ✓
- Real nested settings.json shape verified empirically (done during planning) and encoded in Task 3 tests/impl. ✓
- Round-trip pins hook↔store contract (no shared import) → Task 2 test. ✓
- Packaging the hook in the wheel → Task 8. ✓
- Licensing note (spirit-only) → Task 3 module docstring. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command has expected output. ✓

**Type consistency:** `Identity` fields (`session_id/transcript_path/cwd/source/written_at`) are identical across Task 1 (`write`/`read`), Task 2 (hook record keys), and Task 6 (`resolve`). `read_identity` alias in Task 6 matches the monkeypatch target in its tests. `ensure_installed(settings_path, interpreter, script)` / `uninstall(settings_path)` / `desired_command(interpreter, script)` signatures match their Task 3 tests. `session_identity.prune(live_names, store)` called as `prune(set(sessions))` in Task 7 (store defaulted). ✓
