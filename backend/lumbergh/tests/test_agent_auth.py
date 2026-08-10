import asyncio

import pytest

import lumbergh.agent_token as at
from lumbergh.auth import AuthMiddleware


def _scope(path, headers=None):
    return {"type": "http", "path": path, "headers": headers or []}


async def _passes(mw, scope):
    called = {"app": False}

    async def app(_s, _r, _snd):
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


def _with_token(tmp_path, monkeypatch):
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", tmp_path / "t")
    tok = at.ensure_token()
    monkeypatch.setattr("lumbergh.auth._is_auth_enabled", lambda: True)
    return AuthMiddleware(app=None), [(b"x-lumbergh-agent-token", tok.encode())]


@pytest.mark.parametrize(
    "path",
    [
        "/api/agent/sessions",
        "/api/bill/fleet",
        "/api/bill/spawn",
        "/api/bill/report",
        "/api/worktrees",
        "/api/worktrees/reap",
        # `lb worktree create --agent` starts the session through this one. Exact path
        # only — see the prefix test below.
        "/api/sessions",
    ],
)
def test_the_token_covers_every_path_lb_calls(tmp_path, monkeypatch, path):
    """The token gated `/api/agent` alone, so a Bill on another host was locked out of the
    half of its job that runs through `/api/bill` the moment a password was set."""
    mw, headers = _with_token(tmp_path, monkeypatch)
    assert asyncio.run(_passes(mw, _scope(path, headers)))["app"] is True


@pytest.mark.parametrize(
    "path",
    [
        "/api/sessions/1/git/push",
        "/api/sessions/1/git/force-push",
        "/api/sessions/1/git/reset",
        "/api/sessions/1/files",
        "/api/settings",
    ],
)
def test_the_token_does_not_open_the_rest_of_the_session_api(tmp_path, monkeypatch, path):
    """`/api/sessions` is granted as an exact path, never a prefix. `lb` needs exactly one
    verb there — creating a session — and a prefix grant would hand the same token
    force-push, reset, and the file API, which no `lb` command uses."""
    mw, headers = _with_token(tmp_path, monkeypatch)
    res = asyncio.run(_passes(mw, _scope(path, headers)))
    assert res["app"] is False
    assert res["status"] == 401


def test_a_wrong_token_opens_nothing(tmp_path, monkeypatch):
    mw, _headers = _with_token(tmp_path, monkeypatch)
    scope = _scope("/api/bill/spawn", [(b"x-lumbergh-agent-token", b"not-the-token")])
    assert asyncio.run(_passes(mw, scope))["app"] is False


def test_a_lookalike_prefix_is_not_covered(tmp_path, monkeypatch):
    """`/api/billing` must not ride in on the `/api/bill` grant."""
    mw, headers = _with_token(tmp_path, monkeypatch)
    assert asyncio.run(_passes(mw, _scope("/api/billing/charge", headers)))["app"] is False
