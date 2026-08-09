"""Background fetching for the session you are looking at."""

import subprocess
from pathlib import Path

import pytest

from lumbergh import auto_fetch
from lumbergh.auto_fetch import MAX_BACKOFF_SECONDS, FetchSchedule


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, encoding="utf-8"
    ).stdout.strip()


class TestSchedule:
    def test_a_repo_never_fetched_is_due_now(self):
        schedule = FetchSchedule(cooldown=300)

        assert schedule.due("repo", now=0.0)

    def test_a_fetched_repo_waits_out_the_cooldown(self):
        schedule = FetchSchedule(cooldown=300)
        schedule.succeeded("repo", now=0.0)

        assert not schedule.due("repo", now=299.0)
        assert schedule.due("repo", now=300.0)

    def test_a_zero_cooldown_disables_fetching(self):
        schedule = FetchSchedule(cooldown=0)

        assert not schedule.due("repo", now=10_000.0)

    def test_failures_back_off_further_each_time(self):
        """An offline laptop should get quieter, not keep paying the timeout."""
        schedule = FetchSchedule(cooldown=300)

        schedule.failed("repo", now=0.0)
        assert not schedule.due("repo", now=299.0)

        schedule.failed("repo", now=300.0)
        assert not schedule.due("repo", now=300.0 + 599.0)
        assert schedule.due("repo", now=300.0 + 600.0)

    def test_backoff_is_capped(self):
        schedule = FetchSchedule(cooldown=300)
        for n in range(20):
            schedule.failed("repo", now=float(n))

        assert schedule.due("repo", now=19.0 + MAX_BACKOFF_SECONDS)

    def test_success_clears_the_backoff(self):
        schedule = FetchSchedule(cooldown=300)
        schedule.failed("repo", now=0.0)
        schedule.failed("repo", now=0.0)

        schedule.succeeded("repo", now=0.0)

        assert schedule.due("repo", now=300.0)

    def test_repos_are_scheduled_independently(self):
        schedule = FetchSchedule(cooldown=300)
        schedule.succeeded("one", now=0.0)

        assert not schedule.due("one", now=10.0)
        assert schedule.due("two", now=10.0)


@pytest.fixture
def clone(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "config", "user.email", "t@t.t")
    _git(origin, "config", "user.name", "t")
    (origin / "f").write_text("x")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "init")
    _git(origin, "branch", "landed")

    working = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(working))
    return working, origin


class TestFetch:
    def test_fetch_prunes_branches_deleted_upstream(self, clone):
        working, origin = clone
        _git(origin, "branch", "-D", "landed")

        assert auto_fetch.fetch(working) is True
        assert "origin/landed" not in _git(working, "branch", "-r")

    def test_an_unreachable_remote_reports_failure_rather_than_raising(self, clone, tmp_path):
        working, _origin = clone
        _git(working, "remote", "set-url", "origin", str(tmp_path / "no-such-repo"))

        assert auto_fetch.fetch(working) is False

    def test_worktrees_share_their_repository_key(self, clone, tmp_path):
        """Otherwise a repo with five worktrees pays for five fetches."""
        working, _origin = clone
        sibling = tmp_path / "wt"
        _git(working, "worktree", "add", "-q", "-b", "side", str(sibling))

        assert auto_fetch.repo_key(sibling) == auto_fetch.repo_key(working)

    def test_a_repo_without_a_remote_is_recognised(self, tmp_path, clone):
        working, _origin = clone
        lonely = tmp_path / "lonely"
        lonely.mkdir()
        _git(lonely, "init", "-q")

        assert auto_fetch.has_remote(working) is True
        assert auto_fetch.has_remote(lonely) is False
