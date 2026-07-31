import lumbergh.activity.claude_code as cc
from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.session_identity import Identity


def test_resolve_uses_identity_when_transcript_exists(tmp_path, monkeypatch):
    transcript = tmp_path / "abc.jsonl"
    transcript.write_text("")
    ident = Identity("s1", str(transcript), str(tmp_path), "startup", 1.0)
    monkeypatch.setattr(cc, "read_identity", lambda _name: ident)
    adapter = ClaudeCodeAdapter.resolve("sess", tmp_path)
    assert adapter is not None
    assert adapter.path == transcript


def test_resolve_falls_back_when_transcript_missing(tmp_path, monkeypatch):
    ident = Identity("s1", str(tmp_path / "gone.jsonl"), str(tmp_path), "startup", 1.0)
    monkeypatch.setattr(cc, "read_identity", lambda _name: ident)
    called = {}
    monkeypatch.setattr(
        ClaudeCodeAdapter, "for_cwd", classmethod(lambda _cls, cwd: called.setdefault("cwd", cwd))
    )
    ClaudeCodeAdapter.resolve("sess", tmp_path)
    assert called["cwd"] == tmp_path


def test_resolve_falls_back_when_no_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "read_identity", lambda _name: None)
    called = {}
    monkeypatch.setattr(
        ClaudeCodeAdapter, "for_cwd", classmethod(lambda _cls, cwd: called.setdefault("cwd", cwd))
    )
    ClaudeCodeAdapter.resolve("sess", tmp_path)
    assert called["cwd"] == tmp_path


def test_session_meta_falls_back_to_worktree_registry_for_window_target(monkeypatch):
    from lumbergh.activity.resolve import session_meta

    monkeypatch.setattr("lumbergh.routers.sessions.get_stored_sessions", dict)
    monkeypatch.setattr(
        "lumbergh.worktrees.all_entries",
        lambda: [{"target": "port:fleet-644", "path": "/wt/644"}],
    )
    meta = session_meta("port:fleet-644")
    assert meta["workdir"] == "/wt/644"


def test_session_meta_prefers_session_store_when_present(monkeypatch):
    from lumbergh.activity.resolve import session_meta

    monkeypatch.setattr(
        "lumbergh.routers.sessions.get_stored_sessions",
        lambda: {"scout-1": {"workdir": "/live/scout", "agent_provider": "pi"}},
    )
    meta = session_meta("scout-1")
    assert meta["workdir"] == "/live/scout"
    assert meta["agent_provider"] == "pi"
