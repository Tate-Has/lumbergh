"""Remote-tracking refs for branches that no longer exist upstream.

Fetching adds and updates ``origin/*`` refs but never removes them, so every
squash-merged-and-deleted branch leaves one behind permanently. They accumulate
until they outnumber the live branches, and the git graph draws every one.
"""

import subprocess
from pathlib import Path

import pytest

from lumbergh.git_utils import get_remote_status


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path):
    """A clone of an origin that still has a ``landed`` branch."""
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
    _git(working, "config", "user.email", "t@t.t")
    _git(working, "config", "user.name", "t")
    return working, origin


def _remote_refs(repo: Path) -> set[str]:
    return set(_git(repo, "branch", "-r", "--format=%(refname:short)").splitlines())


def test_clone_starts_with_the_upstream_branch(clone):
    working, _origin = clone

    assert "origin/landed" in _remote_refs(working)


def test_a_branch_deleted_upstream_stops_being_tracked(clone):
    working, origin = clone
    _git(origin, "branch", "-D", "landed")

    get_remote_status(working)

    assert "origin/landed" not in _remote_refs(working)


def test_live_branches_survive(clone):
    working, origin = clone
    _git(origin, "branch", "-D", "landed")

    get_remote_status(working)

    assert "origin/main" in _remote_refs(working)


def test_local_branches_are_untouched(clone):
    """Pruning is bookkeeping about the remote — local work is not its business."""
    working, origin = clone
    _git(working, "checkout", "-q", "-b", "landed", "origin/landed")
    _git(working, "checkout", "-q", "main")
    _git(origin, "branch", "-D", "landed")

    get_remote_status(working)

    assert "landed" in _git(working, "branch", "--format=%(refname:short)").splitlines()
