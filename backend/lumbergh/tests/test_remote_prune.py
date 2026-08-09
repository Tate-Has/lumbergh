"""The refs a plain fetch quietly fails to maintain.

Two of them, both drawn by the git graph and so both visible as wrong:

- **Branches deleted upstream.** Fetching adds and updates ``origin/*`` refs but never
  removes them, so every squash-merged-and-deleted branch leaves one behind permanently.
  They accumulate until they outnumber the live branches.
- **Tags moved upstream.** Git refuses to overwrite a tag ref it already has, so a tag
  that is deleted and recreated at a new commit — which is exactly what a rolling
  release tag like ``alpha`` is — freezes at whatever commit the clone first saw and
  stays there forever.
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


def _second_commit(origin: Path) -> str:
    (origin / "f").write_text("y")
    _git(origin, "commit", "-qam", "second")
    return _git(origin, "rev-parse", "HEAD")


def test_a_tag_moved_upstream_moves_locally(clone):
    """A rolling release tag is deleted and recreated at a new commit on every build.

    Git will not overwrite a tag ref it already has, so without forcing it the clone
    pins the tag to the first commit it ever saw — the badge in the graph then points
    at an old commit indefinitely, which is worse than showing nothing.
    """
    working, origin = clone
    _git(origin, "tag", "alpha")
    get_remote_status(working)
    moved_to = _second_commit(origin)
    _git(origin, "tag", "-f", "alpha")

    get_remote_status(working)

    assert _git(working, "rev-parse", "alpha") == moved_to


def test_a_new_upstream_tag_still_arrives(clone):
    """Tag auto-following already worked; forcing must not cost us it."""
    working, origin = clone
    _git(origin, "tag", "v1.0.0")

    get_remote_status(working)

    assert "v1.0.0" in _git(working, "tag").splitlines()


def test_a_purely_local_tag_is_not_deleted(clone):
    """Tags the user made are theirs. Pruning tags would delete every one of them, which
    is why this fetch forces updates without pruning tags."""
    working, _origin = clone
    _git(working, "tag", "my-own-marker")

    get_remote_status(working)

    assert "my-own-marker" in _git(working, "tag").splitlines()
