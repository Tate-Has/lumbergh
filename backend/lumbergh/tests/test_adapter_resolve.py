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
