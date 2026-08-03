import os

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
    assert {k: v for k, v in captured["json"].items() if k != "caller_pid"} == {
        "run": "r",
        "force": True,
        "dry_run": False,
    }
    # The reaper must spare whatever asked for the teardown, so it has to be told.
    assert captured["json"]["caller_pid"] == os.getpid()


def test_teardown_posts_dry_run(monkeypatch, capsys):
    captured = {}

    def fake_request(_m, _p, **kw):
        captured["json"] = kw.get("json")
        return _Resp(
            {
                "run": "r",
                "dry_run": True,
                "results": [
                    {"target": "r:a", "killed": False, "reaped": "dry-run", "landed": True}
                ],
                "refused": [],
            }
        )

    monkeypatch.setattr(teardown_cli, "_request", fake_request)
    rc = teardown_cli.run({"--run": "r", "--dry-run": True})

    assert rc == 0
    assert {k: v for k, v in captured["json"].items() if k != "caller_pid"} == {
        "run": "r",
        "force": False,
        "dry_run": True,
    }
    assert "dry run" in capsys.readouterr().out


def test_teardown_surfaces_refused(monkeypatch, capsys):
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [{"target": "r:a", "killed": True, "reaped": "refused"}],
                "refused": [{"target": "r:a", "reason": "dirty"}],
            }
        ),
    )
    rc = teardown_cli.run({"--run": "r"})
    out = capsys.readouterr().out
    assert rc == 0
    assert "r:a" in out
    assert "dirty" in out
    assert "force" in out


def test_teardown_shows_which_workers_went_down_unlanded(monkeypatch, capsys):
    """A worker torn down without landing is the one whose tracking issue is now
    stranded — the operator has to see that without going to look for it."""
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [
                    {"target": "r:a", "killed": True, "reaped": "removed", "landed": True},
                    {"target": "r:b", "killed": True, "reaped": "removed", "landed": False},
                ],
                "refused": [],
            }
        ),
    )
    rc = teardown_cli.run({"--run": "r"})
    out = capsys.readouterr().out

    assert rc == 0
    assert "landed" in out
    assert "r:b" in out.split("unlanded")[1]  # called out explicitly, not just tabulated


def test_teardown_separates_landing_nothing_from_losing_work(capsys, monkeypatch):
    """A scout commits nothing, so it is neither landed nor work that went missing.
    Listing it as unlanded is what sends a consumer to reopen an issue that shipped."""
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [
                    {
                        "target": "r:scout",
                        "killed": True,
                        "reaped": "removed",
                        "landed": False,
                        "commits": 0,
                    },
                    {
                        "target": "r:lost",
                        "killed": True,
                        "reaped": "removed",
                        "landed": False,
                        "commits": 3,
                    },
                ],
                "refused": [],
            }
        ),
    )
    rc = teardown_cli.run({"--run": "r"})
    out = capsys.readouterr().out

    assert rc == 0
    assert "r:lost" in out.split("unlanded")[1].split("\n")[0]
    assert "r:scout" not in out.split("unlanded")[1].split("\n")[0]
    assert "r:scout" in out.split("landed nothing")[1]


def test_teardown_does_not_report_a_refused_worker_as_torn_down(capsys, monkeypatch):
    """A refusal leaves the worker standing with its work intact. Announcing it as
    unlanded-and-gone is the same false alarm in the other direction."""
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [
                    {
                        "target": "r:a",
                        "killed": True,
                        "reaped": None,
                        "landed": False,
                        "commits": 2,
                    }
                ],
                "refused": [{"target": "r:a", "reason": "unlanded"}],
            }
        ),
    )
    rc = teardown_cli.run({"--run": "r"})
    out = capsys.readouterr().out

    assert rc == 0
    assert "torn down without landing" not in out
    assert "left running" in out


def test_teardown_renders_an_unanswerable_landed_check_as_unknown(capsys, monkeypatch):
    """Blank reads as false to every consumer downstream. "Could not tell" has to look
    different from "provably did not land"."""
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [
                    {
                        "target": "r:a",
                        "killed": True,
                        "reaped": "removed",
                        "landed": None,
                        "commits": None,
                    }
                ],
                "refused": [],
            }
        ),
    )
    rc = teardown_cli.run({"--run": "r"})
    out = capsys.readouterr().out

    assert rc == 0
    assert "unknown" in out
    assert "unlanded" not in out


def test_teardown_refusal_does_not_tell_a_commit_mode_worker_to_push(capsys, monkeypatch):
    """Under `commit` delivery no worker ever pushes. Telling the operator to push is
    how `--force` became the reflex."""
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [{"target": "r:a", "killed": True, "reaped": None, "landed": False}],
                "refused": [{"target": "r:a", "reason": "unlanded"}],
            }
        ),
    )
    rc = teardown_cli.run({"--run": "r"})
    out = capsys.readouterr().out

    assert rc == 0
    assert "push" not in out
    assert "lb land" in out


def test_teardown_names_every_process_it_killed(monkeypatch, capsys):
    """A leftover server dies quietly otherwise, and the operator learns what teardown
    took only when something they were using stops answering."""
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "results": [
                    {
                        "target": "r:issue-784",
                        "killed": True,
                        "reaped": "removed",
                        "landed": True,
                        "commits": 1,
                        "processes": [
                            {
                                "pid": 1379330,
                                "cmd": "granian --port 40159 app.main:app",
                                "signal": "SIGKILL",
                            }
                        ],
                    }
                ],
                "refused": [],
            }
        ),
    )

    rc = teardown_cli.run({"--run": "r"})

    out = capsys.readouterr().out
    assert rc == 0
    assert "procs" in out
    assert "killed (SIGKILL): r:issue-784 — 1379330 granian --port 40159 app.main:app" in out


def test_teardown_dry_run_says_what_it_would_kill(monkeypatch, capsys):
    monkeypatch.setattr(
        teardown_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "run": "r",
                "dry_run": True,
                "results": [
                    {
                        "target": "r:issue-784",
                        "killed": False,
                        "reaped": "dry-run",
                        "landed": True,
                        "commits": 1,
                        "processes": [{"pid": 1379330, "cmd": "granian app.main:app"}],
                    }
                ],
                "refused": [],
            }
        ),
    )

    rc = teardown_cli.run({"--run": "r", "--dry-run": True})

    out = capsys.readouterr().out
    assert rc == 0
    assert "would kill: r:issue-784 — 1379330 granian app.main:app" in out
