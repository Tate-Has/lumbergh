from lumbergh.agent_cli import teardown as teardown_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_teardown_requires_run(capsys):
    rc = teardown_cli.run({})
    assert rc == 2
    assert "--run" in capsys.readouterr().out


def test_teardown_posts_run_and_force(monkeypatch):
    captured = {}

    def fake_request(_m, _p, **kw):
        captured["json"] = kw.get("json")
        return _Resp({"run": "r", "results": [], "refused": []})

    monkeypatch.setattr(teardown_cli, "_request", fake_request)
    rc = teardown_cli.run({"--run": "r", "--force": True})
    assert rc == 0
    assert captured["json"] == {"run": "r", "force": True}


def test_teardown_surfaces_refused(monkeypatch, capsys):
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [{"target": "r:a", "killed": True, "reaped": "refused"}],
                "refused": ["r:a"],
            }
        ),
    )
    rc = teardown_cli.run({"--run": "r"})
    out = capsys.readouterr().out
    assert rc == 0
    assert "r:a" in out
    assert "force" in out
