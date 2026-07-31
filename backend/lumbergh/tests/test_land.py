import subprocess
from pathlib import Path

import pytest

from lumbergh import land


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo_with_two_branches(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    origin = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", "-q", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "-q", "origin")
    for name in ("feat-a", "feat-b"):
        _git(repo, "checkout", "-q", "-b", name, "master")
        (repo / f"{name}.txt").write_text(name)
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", name)
    _git(repo, "checkout", "-q", "master")
    return repo


def test_assemble_cherry_picks_both_branches(repo_with_two_branches):
    repo = repo_with_two_branches
    result = land.assemble(repo, "r1", "master", ["feat-a", "feat-b"])
    assert result["ok"] is True
    wt = Path(result["worktree"])
    assert (wt / "feat-a.txt").exists()
    assert (wt / "feat-b.txt").exists()
    assert not (repo / "feat-a.txt").exists()  # user's checkout untouched
    land.cleanup_assembly(repo, result["worktree"], result["batch"])
    assert not wt.exists()


def test_assemble_reports_conflict_and_aborts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text("0\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    origin = tmp_path / "o.git"
    _git(repo, "clone", "--bare", "-q", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "-q", "origin")
    for name, val in (("x", "1\n"), ("y", "2\n")):
        _git(repo, "checkout", "-q", "-b", name, "master")
        (repo / "f.txt").write_text(val)
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", name)
    _git(repo, "checkout", "-q", "master")
    result = land.assemble(repo, "r2", "master", ["x", "y"])
    assert result["ok"] is False
    assert result["stage"] == "cherry-pick"
