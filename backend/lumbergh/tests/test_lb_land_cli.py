from lumbergh.agent_cli import land as land_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_land_requires_run(capsys):
    rc = land_cli.run({})
    assert rc == 2
    assert "--run" in capsys.readouterr().out


def test_land_without_push_sends_push_false(monkeypatch):
    captured = {}

    def fake_request(_m, _p, **kw):
        captured["json"] = kw.get("json")
        return _Resp(
            {
                "run": "r",
                "batch": "batch-r",
                "base": "main",
                "pushed": False,
                "smoke": "passed",
                "next": "re-run with --push",
            }
        )

    monkeypatch.setattr(land_cli, "_request", fake_request)
    rc = land_cli.run({"--run": "r", "--onto": "main"})
    assert rc == 0
    assert captured["json"]["push"] is False
    assert captured["json"]["skip_smoke"] is False


def test_land_prints_the_worker_to_commit_mapping(monkeypatch, capsys):
    """Every worker in the batch has to be visible in the output with its commit
    count, so "did all five land?" is answerable by reading, not by counting."""
    monkeypatch.setattr(
        land_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "batch": "batch-r",
                "base": "main",
                "pushed": True,
                "smoke": "passed",
                "picked": {"feat-a": ["aaa1", "aaa2"], "feat-b": ["bbb1"], "feat-c": []},
            }
        ),
    )
    rc = land_cli.run({"--run": "r", "--push": True})
    out = capsys.readouterr().out

    assert rc == 0
    assert "workers[3]" in out
    assert "feat-a,2" in out
    assert "feat-c,0" in out  # a worker that contributed nothing is still listed


def test_land_push_and_skip_smoke_flags(monkeypatch):
    captured = {}

    def fake_request(_m, _p, **kw):
        captured["json"] = kw.get("json")
        return _Resp(
            {"run": "r", "batch": "batch-r", "base": "main", "pushed": True, "smoke": "skipped"}
        )

    monkeypatch.setattr(land_cli, "_request", fake_request)
    rc = land_cli.run({"--run": "r", "--push": True, "--skip-smoke": True})
    assert rc == 0
    assert captured["json"]["push"] is True
    assert captured["json"]["skip_smoke"] is True
