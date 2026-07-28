import io
import json
from unittest.mock import patch

import lumbergh.hooks.lumbergh_session_start as hook


def _fake_urlopen(payload):
    def _open(req, timeout=None):  # noqa: ARG001
        return io.BytesIO(json.dumps(payload).encode())

    return _open


def test_ambient_lists_peers_excluding_self(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path))
    (tmp_path / "agent-token").write_text("tok")
    payload = {
        "sessions": [
            {"name": "me", "state": "working"},
            {"name": "peer-a", "state": "blocked"},
            {"name": "peer-b", "state": "idle"},
        ]
    }
    with patch("urllib.request.urlopen", _fake_urlopen(payload)):
        ctx = hook._ambient_context("startup", "me")
    assert ctx is not None
    assert "peer-a — blocked" in ctx
    assert "peer-b — idle" in ctx
    assert "me —" not in ctx  # self excluded


def test_ambient_skipped_for_non_startup_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path))
    (tmp_path / "agent-token").write_text("tok")
    assert hook._ambient_context("compact", "me") is None
    assert hook._ambient_context("clear", "me") is None


def test_ambient_none_when_no_token(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path))
    assert hook._ambient_context("startup", "me") is None


def test_ambient_none_on_request_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path))
    (tmp_path / "agent-token").write_text("tok")

    def _boom(req, timeout=None):  # noqa: ARG001
        raise OSError("refused")

    with patch("urllib.request.urlopen", _boom):
        assert hook._ambient_context("startup", "me") is None


def test_ambient_none_when_only_self(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path))
    (tmp_path / "agent-token").write_text("tok")
    payload = {"sessions": [{"name": "me", "state": "working"}]}
    with patch("urllib.request.urlopen", _fake_urlopen(payload)):
        assert hook._ambient_context("startup", "me") is None
