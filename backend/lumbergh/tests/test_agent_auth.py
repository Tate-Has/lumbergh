import asyncio

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
