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
