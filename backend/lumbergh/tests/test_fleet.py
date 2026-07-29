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
        ("blocked", False, True),
        ("error", False, True),
        ("dead", False, True),
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
