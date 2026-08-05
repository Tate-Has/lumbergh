"""A worker sitting idle on uncommitted work must be visible and must wake its overseer.

The incident: a worker finished, went `idle`, and sat with 0 commits and 7 uncommitted
files — a 2,237-line harness. `lb fleet --wait` returned "no task needs you yet" on three
consecutive 540 s waits, because the worker had woken its overseer once early on and was
marked seen forever. It is the one state where teardown/reap is the *wrong* move, and
nothing surfaced it.
"""

import pathlib
import subprocess

import pytest

from lumbergh import fleet, worktrees
from lumbergh.routers import bill


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _worker_row(**over):
    row = {
        "role": "worker",
        "state": "idle",
        "unseen": False,
        "task": "issue-668",
        "dirty": 0,
        "commits": 0,
        "outcome": None,
    }
    return {**row, **over}


def test_uncommitted_work_in_a_worktree_is_counted(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    _git(wt, "init", "-q", "-b", "main")
    _git(wt, "config", "user.email", "t@t")
    _git(wt, "config", "user.name", "t")
    (wt / "base.txt").write_text("base")
    _git(wt, "add", ".")
    _git(wt, "commit", "-qm", "base")
    assert worktrees.work_in_progress(wt)["dirty"] == 0

    (wt / "harness.py").write_text("x" * 100)
    (wt / "base.txt").write_text("edited")
    assert worktrees.work_in_progress(wt)["dirty"] == 2  # untracked counts — it is real work


def test_commits_are_counted_from_where_the_worker_was_created(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    _git(wt, "init", "-q", "-b", "main")
    _git(wt, "config", "user.email", "t@t")
    _git(wt, "config", "user.name", "t")
    (wt / "base.txt").write_text("base")
    _git(wt, "add", ".")
    _git(wt, "commit", "-qm", "base")
    base_sha = subprocess.run(
        ["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, encoding="utf-8"
    ).stdout.strip()

    assert worktrees.work_in_progress(wt, base_sha=base_sha)["commits"] == 0
    (wt / "f.txt").write_text("work")
    _git(wt, "add", ".")
    _git(wt, "commit", "-qm", "work")
    assert worktrees.work_in_progress(wt, base_sha=base_sha)["commits"] == 1


def test_an_unreadable_worktree_reports_unknown_never_zero(tmp_path):
    # `dirty: 0` is the "safe to reap" reading. A path git cannot answer for must not
    # borrow it.
    assert worktrees.work_in_progress(tmp_path / "gone") == {"dirty": None, "commits": None}


def test_idle_worker_holding_uncommitted_work_needs_attention():
    assert fleet.needs_attention(_worker_row(dirty=7)) is True


def test_idle_worker_with_a_clean_tree_does_not():
    assert fleet.needs_attention(_worker_row(dirty=0)) is False


def test_an_overseers_own_dirty_checkout_is_not_a_worker_holding_work():
    # An overseer's path is the shared checkout, dirty for the whole of normal
    # development. Waking on it would make supervision useless.
    assert fleet.needs_attention(_worker_row(role="overseer", dirty=12)) is False


def test_unknown_dirtiness_is_not_read_as_holding_work():
    assert fleet.needs_attention(_worker_row(dirty=None)) is False


class TestWakeOnTransition:
    """`--wait` must re-wake on a *transition into* holding-uncommitted-work, even for a
    task it already showed the overseer once."""

    @pytest.fixture(autouse=True)
    def _clean_acks(self):
        bill._holding_acked.clear()
        yield
        bill._holding_acked.clear()

    def _rows(self, **over):
        return [_worker_row(parent="port", **over)]

    def test_first_sighting_wakes_the_overseer(self):
        rows = self._rows(dirty=7)
        assert bill.viewer_woke(rows, "port") is True

    def test_being_shown_it_stops_it_rewaking(self):
        rows = self._rows(dirty=7)
        bill.viewer_woke(rows, "port")
        bill._mark_seen(rows, "port")
        assert bill.viewer_woke(self._rows(dirty=7), "port") is False

    def test_committing_and_going_dirty_again_wakes_afresh(self):
        rows = self._rows(dirty=7)
        bill.viewer_woke(rows, "port")
        bill._mark_seen(rows, "port")

        clean = self._rows(dirty=0, commits=1)
        bill.viewer_woke(clean, "port")
        bill._mark_seen(clean, "port")

        assert bill.viewer_woke(self._rows(dirty=3, commits=1), "port") is True

    def test_a_worker_already_acked_as_done_still_wakes_when_it_holds_work(self):
        # The reported case exactly: it woke once early on, was marked seen, and its
        # *later* transition into holding uncommitted work was silent.
        delivered = self._rows(dirty=0, unseen=True)
        bill.viewer_woke(delivered, "port")
        bill._mark_seen(delivered, "port")
        assert bill.viewer_woke(self._rows(dirty=7, unseen=False), "port") is True


def test_snapshot_reads_real_git_state_for_a_real_worktree(tmp_path, monkeypatch):
    """End to end through `fleet.snapshot`: a worker holding uncommitted work shows it on
    its row and is flagged as needing attention."""
    from tinydb import TinyDB

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "issue-668", str(wt))
    (wt / "harness.py").write_text("a" * 2237)

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    worktrees.record_worktree(
        wt,
        repo,
        "issue-668",
        "t",
        session="issue-668",
        kind="ship",
        origin="bill",
        base_sha=worktrees.head_sha(wt),
    )

    rows = fleet.snapshot(
        {"issue-668": {}},
        state_of=lambda _n: "idle",
        since_of=lambda _n: 60.0,
        unseen_of=lambda _n: False,  # already seen once, the reported case
        live_targets={"issue-668"},
        work_of=lambda p: worktrees.work_in_progress(pathlib.Path(p)),
    )
    db.close()
    worker = next(r for r in rows if r["task"] == "issue-668")
    assert worker["dirty"] == 1
    assert worker["commits"] == 0
    assert fleet.needs_attention(worker) is True
