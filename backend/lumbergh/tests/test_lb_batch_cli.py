from lumbergh.agent_cli import batch as batch_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_batch_requires_repo_run_briefs_kind(capsys):
    rc = batch_cli.run({"--repo": "/w/app"})
    assert rc == 2
    assert "--briefs" in capsys.readouterr().out


def test_batch_rejects_bad_kind(capsys):
    rc = batch_cli.run({"--repo": "/w", "--run": "r", "--briefs": "d", "--kind": "wander"})
    assert rc == 2
    assert "ship" in capsys.readouterr().out


def test_batch_posts_briefs_as_list(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.chdir(tmp_path)

    def fake_request(_m, _p, **kw):
        captured["json"] = kw.get("json")
        return _Resp({"run": "sprint", "session": "sprint", "workers": [], "failed": []})

    monkeypatch.setattr(batch_cli, "_request", fake_request)
    rc = batch_cli.run(
        {"--repo": "/repo", "--run": "sprint", "--briefs": "a.md,b.md", "--kind": "ship"}
    )
    assert rc == 0
    assert [p.rsplit("/", 1)[-1] for p in captured["json"]["briefs"]] == ["a.md", "b.md"]
    assert captured["json"]["run"] == "sprint"
