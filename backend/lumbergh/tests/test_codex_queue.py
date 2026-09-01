import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from lumbergh import agent_input, codex_queue


def _transcript(path: Path, cwd: Path, thread: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_meta", "payload": {"cwd": str(cwd), "session_id": thread}})
        + "\n"
    )


def test_find_thread_uses_newest_transcript_for_the_session_cwd(tmp_path):
    root = tmp_path / "sessions"
    cwd = tmp_path / "bill"
    old = root / "old.jsonl"
    _transcript(old, cwd, "old-thread")
    os.utime(old, (time.time() - 60, time.time() - 60))
    _transcript(root / "new.jsonl", cwd, "new-thread")

    assert codex_queue.find_thread(cwd, root) == "new-thread"


def test_queue_message_uses_codex_queue_without_terminal_input(tmp_path):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    assert codex_queue.queue_message(tmp_path, "wake up", run=run, find=lambda _: "thread-123")
    assert calls[0][0] == ["codex", "queue", "--thread", "thread-123", "--message", "wake up"]


def test_send_prompt_routes_codex_to_the_queue(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(
        agent_input.codex_queue,
        "queue_message",
        lambda cwd, text: sent.append((cwd, text)) or True,
    )

    assert agent_input.send_prompt("bill:{start}", "wake up", "codex", tmp_path)
    assert sent == [(tmp_path, "wake up")]
