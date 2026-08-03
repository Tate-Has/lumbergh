"""`--base <branch>` must not silently branch off a stale local ref.

`lb land --push` advances the remote without fast-forwarding the local branch, so
the local `dev` a spawn resolves can be commits behind what everyone else calls
`dev`. A worker branched there cannot see work that already landed, and nothing in
the spawn output says which commit it started from.
"""

import subprocess
from pathlib import Path

import pytest

from lumbergh import worktrees
from lumbergh.git_utils import resolve_spawn_base


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, encoding="utf-8"
    ).stdout.strip()


def _sha(cwd: Path, ref: str) -> str:
    return _git(cwd, "rev-parse", ref)


def _commit(cwd: Path, name: str) -> str:
    (cwd / name).write_text(name)
    _git(cwd, "add", ".")
    _git(cwd, "commit", "-qm", name)
    return _sha(cwd, "HEAD")


@pytest.fixture
def clone(tmp_path):
    """A clone of an origin whose `dev` both sides start out agreeing on."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init", "-q", "-b", "dev")
    _git(upstream, "config", "user.email", "t@t")
    _git(upstream, "config", "user.name", "t")
    _commit(upstream, "base")

    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(upstream), str(local))
    _git(local, "config", "user.email", "t@t")
    _git(local, "config", "user.name", "t")
    return local, upstream


def _advance_remote(local: Path, upstream: Path) -> str:
    """Land a commit the way `lb land --push` does: remote moves, local `dev` doesn't."""
    sha = _commit(upstream, "landed")
    _git(local, "fetch", "-q", "origin")
    return sha


def test_resolves_a_stale_local_base_to_its_upstream(clone):
    local, upstream = clone
    landed = _advance_remote(local, upstream)

    resolved = resolve_spawn_base(local, "dev")

    assert resolved["sha"] == landed
    assert resolved["ref"] == "origin/dev"
    assert "behind" in resolved["note"]


def test_keeps_unpushed_local_work_as_the_base_and_says_so(clone):
    local, _ = clone
    ahead = _commit(local, "unpushed")

    resolved = resolve_spawn_base(local, "dev")

    assert resolved["sha"] == ahead
    assert resolved["ref"] == "dev"
    assert "ahead" in resolved["note"]


def test_says_nothing_when_local_and_upstream_agree(clone):
    local, _ = clone

    resolved = resolve_spawn_base(local, "dev")

    assert resolved["sha"] == _sha(local, "dev")
    assert resolved["note"] == ""


def test_reports_the_base_sha_for_a_branch_with_no_upstream(clone):
    local, _ = clone
    _git(local, "branch", "solo")

    resolved = resolve_spawn_base(local, "solo")

    assert resolved["ref"] == "solo"
    assert resolved["sha"] == _sha(local, "solo")
    assert resolved["note"] == ""


@pytest.mark.usefixtures("worktrees_db")
def test_create_branches_the_worktree_off_the_landed_commit(clone, tmp_path):
    local, upstream = clone
    landed = _advance_remote(local, upstream)

    created = worktrees.create(
        local,
        "worker",
        created_at="now",
        create_branch=True,
        base_branch="dev",
        global_base_dir=str(tmp_path / "wts"),
    )

    assert "error" not in created
    assert _sha(Path(created["path"]), "HEAD") == landed
    assert created["base"]["sha"] == landed
    assert worktrees.get_entry(Path(created["path"]))["base_sha"] == landed


@pytest.fixture
def worktrees_db(tmp_path, monkeypatch):
    from tinydb import TinyDB

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    yield db
    db.close()
