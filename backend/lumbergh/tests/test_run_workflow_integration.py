import subprocess

import pytest

from lumbergh.routers import bill
from lumbergh.runs import run_members


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo_with_run(tmp_path):
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


def test_land_run_assembles_a_real_run_without_touching_the_checkout(monkeypatch, repo_with_run):
    repo = repo_with_run
    members = [
        {"target": "sprint:feat-a", "branch": "feat-a", "parent_repo": str(repo), "run": "sprint"},
        {"target": "sprint:feat-b", "branch": "feat-b", "parent_repo": str(repo), "run": "sprint"},
    ]
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: members)
    assert [m["target"] for m in run_members("sprint")] == ["sprint:feat-a", "sprint:feat-b"]

    resp = bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, skip_smoke=True))

    assert resp["pushed"] is False
    assert set(resp["picked"]) == {"feat-a", "feat-b"}
    assert not (repo / "feat-a.txt").exists()  # user's master checkout untouched
