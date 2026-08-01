import pytest

from lumbergh import fleet, worktrees


@pytest.fixture
def registry(tmp_path, monkeypatch):
    from tinydb import TinyDB

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    yield db
    db.close()


def _fake_reconcile(rows_by_repo):
    def reconcile(repo, live_sessions):  # noqa: ARG001
        return rows_by_repo.get(str(repo), [])

    return reconcile


@pytest.mark.usefixtures("registry")
def test_snapshot_spans_every_repo_in_the_registry(tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    worktrees.record_worktree(
        tmp_path / "b-wt", tmp_path / "b", "feat/b", "t", session="w-b", kind="scout", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": "w-a",
                        "agent": "claude-code",
                        "state": "active",
                    }
                ],
                str((tmp_path / "b").resolve()): [
                    {
                        "path": str((tmp_path / "b-wt").resolve()),
                        "repo": "b",
                        "branch": "feat/b",
                        "session": "w-b",
                        "agent": "claude-code",
                        "state": "active",
                    }
                ],
            }
        ),
    )
    rows = fleet.snapshot(
        {"w-a": {}, "w-b": {}},
        state_of=lambda n: "working",  # noqa: ARG005
        since_of=lambda n: 12.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
    )
    assert {r["task"] for r in rows} == {"w-a", "w-b"}
    assert {r["kind"] for r in rows} == {"ship", "scout"}


@pytest.mark.usefixtures("registry")
def test_snapshot_includes_overseers_and_nests_workers(tmp_path, monkeypatch):
    """Bill's fleet is overseer-centric: live direct sessions are overseer rows,
    and a worker nests under the overseer whose workdir is the worker's repo."""
    worktrees.record_worktree(
        tmp_path / "port-wt",
        tmp_path / "port",
        "issue-668",
        "t",
        session="issue-668",
        kind="ship",
        origin="bill",
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "port").resolve()): [
                    {
                        "path": str((tmp_path / "port-wt").resolve()),
                        "repo": "port",
                        "branch": "issue-668",
                        "session": "issue-668",
                        "agent": "claude-code",
                        "state": "active",
                    }
                ]
            }
        ),
    )
    live_sessions = {
        "port": {"workdir": str(tmp_path / "port"), "type": "direct"},
        "issue-668": {"workdir": str(tmp_path / "port-wt"), "type": "worktree"},
        "bill": {"workdir": str(tmp_path / "bill"), "type": "direct"},
    }
    rows = fleet.snapshot(
        live_sessions,
        state_of=lambda n: "idle",  # noqa: ARG005
        since_of=lambda n: 5.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
        live_targets={"port", "issue-668", "bill"},
        overseer_exclude={"bill"},
    )
    by_task = {r["task"]: r for r in rows}
    assert by_task["port"]["role"] == "overseer"
    assert by_task["issue-668"]["role"] == "worker"
    assert by_task["issue-668"]["parent"] == "port"
    assert "bill" not in by_task  # Bill never rows himself


@pytest.mark.usefixtures("registry")
def test_snapshot_excludes_batch_container_session(tmp_path, monkeypatch):
    """A batch run's container session (holds worker windows) is not an overseer."""
    worktrees.record_worktree(
        tmp_path / "w1",
        tmp_path / "port",
        "b1",
        "t",
        target="batch:w1",
        kind="ship",
        origin="bill",
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "port").resolve()): [
                    {
                        "path": str((tmp_path / "w1").resolve()),
                        "repo": "port",
                        "branch": "b1",
                        "session": None,
                        "agent": "claude-code",
                        "state": "active",
                    }
                ]
            }
        ),
    )
    live_sessions = {
        "batch": {"workdir": str(tmp_path / "batchdir"), "type": "direct"},
        "port": {"workdir": str(tmp_path / "port"), "type": "direct"},
    }
    rows = fleet.snapshot(
        live_sessions,
        state_of=lambda n: "working",  # noqa: ARG005
        since_of=lambda n: 1.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
        live_targets={"batch:w1", "port"},
        overseer_exclude={"bill"},
    )
    by_task = {r["task"]: r for r in rows}
    assert "batch" not in by_task  # container of worker windows, not an overseer
    assert by_task["batch:w1"]["role"] == "worker"
    assert by_task["port"]["role"] == "overseer"


@pytest.mark.usefixtures("registry")
def test_snapshot_origin_narrows_workers_but_not_overseers(tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "port-wt",
        tmp_path / "port",
        "issue-668",
        "t",
        session="issue-668",
        kind="ship",
        origin="someone-else",
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "port").resolve()): [
                    {
                        "path": str((tmp_path / "port-wt").resolve()),
                        "repo": "port",
                        "branch": "issue-668",
                        "session": "issue-668",
                        "agent": "claude-code",
                        "state": "active",
                    }
                ]
            }
        ),
    )
    live_sessions = {
        "port": {"workdir": str(tmp_path / "port"), "type": "direct"},
        "issue-668": {"workdir": str(tmp_path / "port-wt"), "type": "worktree"},
    }
    rows = fleet.snapshot(
        live_sessions,
        state_of=lambda n: "idle",  # noqa: ARG005
        since_of=lambda n: 5.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
        origin="bill",  # narrows workers to bill-origin only
        live_targets={"port", "issue-668"},
        overseer_exclude={"bill"},
    )
    by_task = {r["task"]: r for r in rows}
    assert "issue-668" not in by_task  # filtered out by origin
    assert by_task["port"]["role"] == "overseer"  # overseer still visible


@pytest.mark.usefixtures("registry")
def test_snapshot_marks_a_registry_row_with_a_dead_session(tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": None,
                        "agent": None,
                        "state": "orphan",
                    }
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {},
        state_of=lambda n: "idle",  # noqa: ARG005
        since_of=lambda n: 0.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
    )
    assert rows[0]["state"] == "dead"
    assert rows[0]["task"] == "w-a"


@pytest.mark.usefixtures("registry")
def test_snapshot_marks_a_dead_row_seen_only_once_acknowledged(tmp_path, monkeypatch):
    # A dead task has no live session to carry the seen/unseen overlay, so its `unseen`
    # comes from `dead_acked`: the paths Bill has already been shown. Fresh -> unseen ->
    # wakes once; acknowledged -> seen -> quiet. This is what stops the reap-refused loop.
    path = str((tmp_path / "a-wt").resolve())
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": path,
                        "repo": "a",
                        "branch": "feat/a",
                        "session": None,
                        "agent": None,
                        "state": "orphan",
                    }
                ]
            }
        ),
    )

    def snap(dead_acked):
        return fleet.snapshot(
            {},
            state_of=lambda n: "idle",  # noqa: ARG005
            since_of=lambda n: 0.0,  # noqa: ARG005
            unseen_of=lambda n: False,  # noqa: ARG005
            dead_acked=dead_acked,
        )

    assert snap(set())[0]["unseen"] is True
    assert snap({path})[0]["unseen"] is False


@pytest.mark.usefixtures("registry")
def test_snapshot_uses_live_state_for_an_active_session(tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": "w-a",
                        "agent": "pi",
                        "state": "active",
                    }
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {"w-a": {}},
        state_of=lambda n: "blocked",  # noqa: ARG005
        since_of=lambda n: 41.6,  # noqa: ARG005
        unseen_of=lambda n: True,  # noqa: ARG005
    )
    assert rows[0]["state"] == "blocked"
    assert rows[0]["since"] == 42
    assert rows[0]["unseen"] is True


@pytest.mark.usefixtures("registry")
def test_snapshot_filters_by_origin(tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", origin="bill"
    )
    worktrees.record_worktree(tmp_path / "h-wt", tmp_path / "a", "feat/h", "t", session="w-h")
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": "w-a",
                        "agent": "pi",
                        "state": "active",
                    },
                    {
                        "path": str((tmp_path / "h-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/h",
                        "session": "w-h",
                        "agent": "pi",
                        "state": "active",
                    },
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {"w-a": {}, "w-h": {}},
        state_of=lambda n: "working",  # noqa: ARG005
        since_of=lambda n: 1.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
        origin="bill",
    )
    assert [r["task"] for r in rows] == ["w-a"]


@pytest.mark.parametrize(
    ("state", "unseen", "expected"),
    [
        # Intrinsic (role-agnostic): a row has an unhandled action when it is stuck
        # (blocked/error) or finished a chunk unseen (idle+unseen). WHICH watcher it wakes
        # is decided by scope (bill._direct_reports), not here.
        ("blocked", False, True),
        ("error", False, True),
        ("idle", True, True),
        ("idle", False, False),
        ("working", False, False),
        ("working", True, False),
    ],
)
def test_needs_attention(state, unseen, expected):
    assert fleet.needs_attention({"state": state, "unseen": unseen}) is expected


def test_any_needs_attention():
    calm = [{"state": "working", "unseen": False}]
    assert fleet.any_needs_attention(calm) is False
    assert fleet.any_needs_attention([*calm, {"state": "blocked", "unseen": False}]) is True


def test_parse_outcome_finds_a_delivered_line():
    text = "ran the tests\nall green\nDELIVERED: https://github.com/o/r/pull/42"
    assert fleet.parse_outcome(text) == "DELIVERED: https://github.com/o/r/pull/42"


def test_parse_outcome_finds_a_failed_line():
    assert fleet.parse_outcome("tried it\nFAILED: the migration needs a decision") == (
        "FAILED: the migration needs a decision"
    )


def test_parse_outcome_takes_the_last_line_when_a_worker_repeats_itself():
    text = "DELIVERED: branch-one\nactually, one more fix\nDELIVERED: branch-two"
    assert fleet.parse_outcome(text) == "DELIVERED: branch-two"


def test_parse_outcome_ignores_a_mention_inside_prose():
    assert fleet.parse_outcome("I will end with DELIVERED: <url> when I finish") is None


def test_parse_outcome_returns_none_without_an_outcome_line():
    assert fleet.parse_outcome("still working on it") is None
    assert fleet.parse_outcome("") is None


@pytest.mark.usefixtures("registry")
def test_snapshot_shows_a_live_window_worker_by_its_monitored_state(tmp_path, monkeypatch):
    """A window worker (spawned via `--into`) is never stored in `live_sessions`, so
    `row["session"]` is None even while it's running. Only `live_targets` (the idle
    monitor's cache) knows it's alive; without that signal the row falls to `dead`."""
    worktrees.record_worktree(
        tmp_path / "a-wt",
        tmp_path / "a",
        "feat/a",
        "t",
        target="port:fleet-644",
        kind="ship",
        origin="bill",
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": None,
                        "agent": None,
                        "state": "orphan",
                    }
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {},
        state_of=lambda n: "working" if n == "port:fleet-644" else "dead",
        since_of=lambda n: 0.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
        live_targets={"port:fleet-644"},
    )
    assert rows[0]["state"] == "working"
    assert rows[0]["session"] is None
    assert rows[0]["target"] == "port:fleet-644"


@pytest.mark.usefixtures("registry")
def test_snapshot_marks_a_window_worker_dead_once_its_target_is_gone(tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt",
        tmp_path / "a",
        "feat/a",
        "t",
        target="port:fleet-644",
        kind="ship",
        origin="bill",
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": None,
                        "agent": None,
                        "state": "orphan",
                    }
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {},
        state_of=lambda n: "working",  # noqa: ARG005
        since_of=lambda n: 0.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
        live_targets=set(),
    )
    assert rows[0]["state"] == "dead"


@pytest.mark.usefixtures("registry")
def test_snapshot_carries_both_paths_bill_needs_to_act(tmp_path, monkeypatch):
    """``repo`` is only a basename, so it cannot feed ``lb spawn --repo``, and the worktree
    path is what ``lb worktree reap`` takes. Without both on the row Bill has no source for
    either and would invent one."""
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": "w-a",
                        "agent": "pi",
                        "state": "active",
                    }
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {"w-a": {}},
        state_of=lambda n: "working",  # noqa: ARG005
        since_of=lambda n: 1.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
    )
    assert rows[0]["repo"] == "a"
    assert rows[0]["repo_path"] == str((tmp_path / "a").resolve())
    assert rows[0]["path"] == str((tmp_path / "a-wt").resolve())
