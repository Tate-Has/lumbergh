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
    assert captured["json"]["create_branch"] is True
    assert captured["json"]["branch"] == "feat"
