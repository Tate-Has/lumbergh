from lumbergh.agent_cli import worktree as wt_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_ls_renders_table(monkeypatch, capsys):
    monkeypatch.setattr(
        wt_cli,
        "_request",
        lambda method, path, **kw: _Resp(  # noqa: ARG005
            {
                "worktrees": [
                    {
                        "path": "/w/app-worktrees/x",
                        "repo": "app",
                        "branch": "x",
                        "session": None,
                        "agent": None,
                        "state": "orphan",
                    }
                ]
            }
        ),
    )
    rc = wt_cli.run("ls", {"--repo": "/w/app"}, [])
    out = capsys.readouterr().out
    assert rc == 0
    assert "orphan" in out
    assert "app-worktrees/x" in out


def test_reap_requires_path(capsys):
    rc = wt_cli.run("reap", {}, [])
    assert rc == 2
    assert "path" in capsys.readouterr().out.lower()


def test_create_posts_expected_body(monkeypatch):
    captured = {}

    def fake_request(method, path, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kw.get("json")
        return _Resp({"path": "/w/app-worktrees/feat", "links_applied": []})

    monkeypatch.setattr(wt_cli, "_request", fake_request)
    rc = wt_cli.run("create", {"--repo": "/w/app", "--branch": "feat", "--new": True}, [])
    assert rc == 0
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/worktrees"
    assert captured["json"]["create_branch"] is True
    assert captured["json"]["branch"] == "feat"


def test_create_with_agent_launches_a_driveable_session(monkeypatch, capsys):
    # A hand-off: worktree + an interactive session the user drives, with the requested
    # agent. This goes through the session-create path (mode=worktree) — not `spawn`, so
    # there is no brief and no autonomous supervision.
    captured = {}

    def fake_request(method, path, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kw.get("json")
        return _Resp({"name": "feat", "workdir": "/w/app-worktrees/feat"})

    monkeypatch.setattr(wt_cli, "_request", fake_request)
    rc = wt_cli.run(
        "create",
        {"--repo": "/w/app", "--branch": "feat", "--new": True, "--agent": "pi"},
        [],
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert captured["path"] == "/api/sessions"
    body = captured["json"]
    assert body["mode"] == "worktree"
    assert body["agent_provider"] == "pi"
    assert body["worktree"] == {
        "parent_repo": "/w/app",
        "branch": "feat",
        "create_branch": True,
        "base_branch": None,
    }
    assert body["name"] == "feat"  # derived from the branch when --session is omitted
    assert "pi" in out


def test_create_with_agent_surfaces_a_session_error(monkeypatch):
    monkeypatch.setattr(
        wt_cli,
        "_request",
        lambda m, p, **kw: _Resp({"detail": "Session 'feat' already exists"}, status=409),  # noqa: ARG005
    )
    rc = wt_cli.run("create", {"--repo": "/w/app", "--branch": "feat", "--agent": "pi"}, [])
    assert rc == 1
