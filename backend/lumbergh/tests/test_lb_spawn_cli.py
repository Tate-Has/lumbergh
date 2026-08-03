from lumbergh.agent_cli import spawn as spawn_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_spawn_requires_repo_branch_kind_and_brief(capsys):
    rc = spawn_cli.run({"--repo": "/w/app"})
    out = capsys.readouterr().out
    assert rc == 2
    assert "--brief" in out


def test_spawn_rejects_a_bad_kind_before_calling_the_server(capsys):
    rc = spawn_cli.run(
        {"--repo": "/w/app", "--branch": "feat/x", "--kind": "wander", "--brief": "/w/b.md"}
    )
    assert rc == 2
    assert "ship" in capsys.readouterr().out


def test_spawn_does_not_call_the_server_on_a_usage_error(monkeypatch):
    called = []
    monkeypatch.setattr(spawn_cli, "_request", lambda m, p, **kw: called.append(1))  # noqa: ARG005

    rc = spawn_cli.run({"--repo": "/w/app"})

    assert rc == 2
    assert not called


def test_spawn_posts_the_expected_body(monkeypatch, capsys):
    captured = {}

    def fake_request(method, path, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kw.get("json")
        return _Resp(
            {
                "session": "feat-x",
                "path": "/w/app-worktrees/feat-x",
                "branch": "feat/x",
                "kind": "ship",
                "brief_path": "/w/b.md",
            }
        )

    monkeypatch.setattr(spawn_cli, "_request", fake_request)
    rc = spawn_cli.run(
        {
            "--repo": "/w/app",
            "--branch": "feat/x",
            "--kind": "ship",
            "--brief": "/w/b.md",
            "--new": True,
            "--intent": "fix the flaky login test",
        }
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert captured["path"] == "/api/bill/spawn"
    assert captured["json"]["create_branch"] is True
    assert captured["json"]["kind"] == "ship"
    assert captured["json"]["task_intent"] == "fix the flaky login test"
    assert "feat-x" in out


def test_spawn_prints_what_it_branched_from(monkeypatch, capsys):
    monkeypatch.setattr(
        spawn_cli,
        "_request",
        lambda m, p, **kw: _Resp(  # noqa: ARG005
            {
                "session": "issue-835",
                "path": "/w/app-worktrees/issue-835",
                "branch": "issue-835",
                "kind": "ship",
                "base_ref": "origin/dev",
                "base_sha": "f91381de1c0ffee0000000000000000000000000",
                "base_note": "local dev (9d351d7e) is behind origin/dev (f91381de)",
            }
        ),
    )

    rc = spawn_cli.run(
        {"--repo": "/w/app", "--branch": "issue-835", "--kind": "ship", "--brief": "/w/b.md"}
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "origin/dev" in out
    assert "f91381de" in out
    assert "is behind" in out


def test_spawn_omits_the_base_note_when_there_is_nothing_to_warn_about(monkeypatch, capsys):
    monkeypatch.setattr(
        spawn_cli,
        "_request",
        lambda m, p, **kw: _Resp(  # noqa: ARG005
            {
                "session": "s",
                "path": "/p",
                "branch": "b",
                "kind": "ship",
                "base_ref": "dev",
                "base_sha": "abc1234500000000000000000000000000000000",
                "base_note": None,
            }
        ),
    )

    spawn_cli.run({"--repo": "/w/app", "--branch": "b", "--kind": "ship", "--brief": "/w/b.md"})

    out = capsys.readouterr().out
    assert "abc12345" in out
    assert "base_note" not in out


def test_spawn_surfaces_the_server_stage_and_help(monkeypatch, capsys):
    monkeypatch.setattr(
        spawn_cli,
        "_request",
        lambda m, p, **kw: _Resp(  # noqa: ARG005
            {
                "detail": {
                    "stage": "worktree",
                    "error": "branch already checked out",
                    "help": "fix the branch or repo and retry",
                }
            },
            status=400,
        ),
    )
    rc = spawn_cli.run(
        {"--repo": "/w/app", "--branch": "feat/x", "--kind": "ship", "--brief": "/w/b.md"}
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "already checked out" in out
    assert "retry" in out


def test_spawn_surfaces_the_delivery_stage(monkeypatch, capsys):
    monkeypatch.setattr(
        spawn_cli,
        "_request",
        lambda m, p, **kw: _Resp(  # noqa: ARG005
            {
                "detail": {
                    "stage": "delivery",
                    "error": "brief could not be delivered after retries",
                    "help": "retry the spawn; the worktree and worker were torn down",
                }
            },
            status=400,
        ),
    )
    rc = spawn_cli.run(
        {"--repo": "/w/app", "--branch": "feat/x", "--kind": "ship", "--brief": "/w/b.md"}
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "delivery" in out
    assert "torn down" in out


def test_spawn_sends_an_absolute_brief_path_for_a_relative_flag(monkeypatch, tmp_path):
    """Bill's cwd is his home and AGENTS.md has him pass ``--brief briefs/<slug>.md``, so a
    relative path is relative to *his* cwd. The wire must always carry an absolute path —
    the server's cwd is unrelated and it cannot recover the intent from a bare path."""
    captured = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        spawn_cli,
        "_request",
        lambda m, p, **kw: (  # noqa: ARG005
            captured.update(kw.get("json"))
            or _Resp(
                {
                    "session": "flaky-login",
                    "path": "/w/app-worktrees/flaky-login",
                    "branch": "feat/x",
                    "kind": "ship",
                    "brief_path": captured["brief_path"],
                }
            )
        ),
    )

    rc = spawn_cli.run(
        {
            "--repo": "/w/app",
            "--branch": "feat/x",
            "--kind": "ship",
            "--brief": "briefs/flaky-login.md",
        }
    )

    assert rc == 0
    assert captured["brief_path"] == str(tmp_path.resolve() / "briefs" / "flaky-login.md")


def test_spawn_leaves_an_already_absolute_brief_path_alone(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        spawn_cli,
        "_request",
        lambda m, p, **kw: (  # noqa: ARG005
            captured.update(kw.get("json"))
            or _Resp({"session": "s", "path": "/p", "branch": "b", "kind": "ship"})
        ),
    )
    absolute = tmp_path / "elsewhere" / "b.md"

    spawn_cli.run({"--repo": "/w/app", "--branch": "b", "--kind": "ship", "--brief": str(absolute)})

    assert captured["brief_path"] == str(absolute)


def test_spawn_cli_sends_into_and_run(monkeypatch):
    captured = {}

    def fake_request(_method, _path, **kw):
        captured["json"] = kw.get("json")
        return _Resp(
            {
                "session": "port:fleet-644",
                "kind": "ship",
                "branch": "kb-644",
                "path": "/wt/644",
            }
        )

    monkeypatch.setattr(spawn_cli, "_request", fake_request)

    rc = spawn_cli.run(
        {
            "--repo": "/repo/port",
            "--branch": "kb-644",
            "--kind": "ship",
            "--brief": "briefs/x.md",
            "--into": "port",
            "--run": "batch-9",
        }
    )
    assert rc == 0
    assert captured["json"]["into"] == "port"
    assert captured["json"]["run"] == "batch-9"
