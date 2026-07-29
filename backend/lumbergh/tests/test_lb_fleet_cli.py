import json

from lumbergh.agent_cli import fleet as fleet_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


_ROW = {
    "task": "w-a",
    "repo": "app",
    "branch": "feat/a",
    "session": "w-a",
    "kind": "ship",
    "state": "blocked",
    "since": 42,
    "unseen": False,
    "outcome": None,
    "path": "/w/app-worktrees/feat-a",
}


def test_fleet_renders_table(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"total": 1, "tasks": [_ROW]}),  # noqa: ARG005
    )
    rc = fleet_cli.run({})
    out = capsys.readouterr().out
    assert rc == 0
    assert "blocked" in out
    assert "w-a" in out


def test_fleet_json_emits_raw_rows(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"total": 1, "tasks": [_ROW]}),  # noqa: ARG005
    )
    rc = fleet_cli.run({"--json": True})
    assert rc == 0
    assert json.loads(capsys.readouterr().out)[0]["task"] == "w-a"


def test_fleet_shows_a_finished_workers_outcome(monkeypatch, capsys):
    finished = dict(_ROW, state="idle", unseen=True, outcome="DELIVERED: https://x.test/pull/7")
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"total": 1, "tasks": [finished]}),  # noqa: ARG005
    )
    rc = fleet_cli.run({})
    out = capsys.readouterr().out
    assert rc == 0
    assert "DELIVERED" in out


def test_fleet_reports_an_empty_fleet(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"total": 0, "tasks": []}),  # noqa: ARG005
    )
    rc = fleet_cli.run({})
    assert rc == 0
    assert "0" in capsys.readouterr().out


def test_wait_hits_the_wait_endpoint_and_reports_the_wake(monkeypatch, capsys):
    captured = {}

    def fake_request(_method, path, **kw):
        captured["path"] = path
        captured["params"] = kw.get("params")
        return _Resp({"woke": True, "waited": 12.5, "total": 1, "tasks": [_ROW]})

    monkeypatch.setattr(fleet_cli, "_request", fake_request)
    rc = fleet_cli.run({"--wait": True, "--timeout": "600"})
    out = capsys.readouterr().out
    assert rc == 0
    assert captured["path"] == "/api/bill/fleet/wait"
    assert captured["params"]["timeout"] == "600"
    assert "blocked" in out


def test_wait_timeout_is_not_an_error(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp(  # noqa: ARG005
            {"woke": False, "waited": 300.0, "total": 1, "tasks": [dict(_ROW, state="working")]}
        ),
    )
    rc = fleet_cli.run({"--wait": True})
    out = capsys.readouterr().out
    assert rc == 0
    assert "no task needs you" in out.lower()


def test_wait_client_timeout_outlives_server_timeout(monkeypatch):
    captured = {}

    def fake_request(_method, _path, **kw):
        captured["timeout"] = kw.get("timeout")
        return _Resp({"woke": False, "waited": 600.0, "total": 0, "tasks": []})

    monkeypatch.setattr(fleet_cli, "_request", fake_request)
    fleet_cli.run({"--wait": True, "--timeout": "600"})
    assert captured["timeout"] > 600


def test_wait_with_empty_fleet_still_reports_the_wait_outcome(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"woke": False, "waited": 300.0, "total": 0, "tasks": []}),  # noqa: ARG005
    )
    rc = fleet_cli.run({"--wait": True})
    out = capsys.readouterr().out
    assert rc == 0
    assert "no task needs you" in out.lower()


def test_wait_rejects_a_non_numeric_timeout(monkeypatch):
    called = []
    monkeypatch.setattr(fleet_cli, "_request", lambda m, p, **kw: called.append(1))  # noqa: ARG005

    rc = fleet_cli.run({"--wait": True, "--timeout": "abc"})

    assert rc == 2
    assert not called


def test_fleet_table_shows_the_paths_bill_must_not_type_from_memory(monkeypatch, capsys):
    """`lb spawn --repo` needs a real path (REPO is a basename) and `lb worktree reap` needs
    the worktree path, and AGENTS.md tells Bill to copy both out of this table."""
    row = dict(_ROW, repo_path="/w/app")
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"total": 1, "tasks": [row]}),  # noqa: ARG005
    )
    rc = fleet_cli.run({})
    out = capsys.readouterr().out
    assert rc == 0
    assert "repo_path" in out
    assert "/w/app" in out
    assert "/w/app-worktrees/feat-a" in out


def test_fleet_table_shows_a_dash_for_a_row_with_no_registered_repo_path(monkeypatch, capsys):
    """An orphan worktree has no registry row, so it has no repo path — that must render as
    a visible gap, not as an empty cell Bill could mistake for a usable value."""
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"total": 1, "tasks": [dict(_ROW, repo_path=None)]}),  # noqa: ARG005
    )
    assert fleet_cli.run({}) == 0
    cells = capsys.readouterr().out.splitlines()[1].strip().split(",")
    assert cells[fleet_cli._COLS.index("repo_path")] == "-"
