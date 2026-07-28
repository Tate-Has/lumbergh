import lumbergh.activity.resolve as r
from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.activity.pi import PiAdapter


def test_provider_pi_prefers_pi(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda *_a: "PI"))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda *_a: "CLAUDE"))
    assert r.resolve_adapter("s", "/w", "pi") == "PI"


def test_provider_claude_prefers_claude(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda *_a: "PI"))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda *_a: "CLAUDE"))
    assert r.resolve_adapter("s", "/w", "claude") == "CLAUDE"


def test_falls_back_to_other(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda *_a: None))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda *_a: "CLAUDE"))
    assert r.resolve_adapter("s", "/w", "pi") == "CLAUDE"


def test_none_when_neither(monkeypatch):
    monkeypatch.setattr(PiAdapter, "resolve", classmethod(lambda *_a: None))
    monkeypatch.setattr(ClaudeCodeAdapter, "resolve", classmethod(lambda *_a: None))
    assert r.resolve_adapter("s", "/w", "claude") is None
