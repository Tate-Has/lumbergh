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


def _branch_exists(repo, branch) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", branch],
            capture_output=True,
        ).returncode
        == 0
    )


def test_teardown_kills_a_bare_session_worker(monkeypatch, tmp_path):
    members = [
        {
            "target": "issue-668",  # a standalone worker → bare session, no window
            "branch": "issue-668",
            "parent_repo": str(tmp_path),
            "path": str(tmp_path / "wt"),
            "run": "port-668",
        }
    ]
    monkeypatch.setattr("lumbergh.routers.bill.run_members", lambda _run: members)
    monkeypatch.setattr("lumbergh.worktrees.reap", lambda _p, **_k: {"status": "removed"})
    monkeypatch.setattr("lumbergh.land.delete_batch", lambda *_a: True)

    killed_sessions = []
    monkeypatch.setattr(
        "lumbergh.routers.bill.kill_tmux_session",
        lambda s: killed_sessions.append(s) or True,
    )

    def _no_window_kill(target):
        raise AssertionError(f"a bare session must not be torn down as a window: {target}")

    monkeypatch.setattr("lumbergh.routers.bill.kill_tmux_window", _no_window_kill)

    resp = bill.teardown(bill.TeardownBody(run="port-668"))

    assert killed_sessions == ["issue-668"]
    assert resp["results"][0]["killed"] is True
    assert resp["refused"] == []


def test_no_push_land_leaves_a_durable_batch_branch(monkeypatch, repo_with_run):
    repo = repo_with_run
    members = [
        {"target": "sprint:feat-a", "branch": "feat-a", "parent_repo": str(repo), "run": "sprint"},
        {"target": "sprint:feat-b", "branch": "feat-b", "parent_repo": str(repo), "run": "sprint"},
    ]
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: members)

    resp = bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, skip_smoke=True))

    # The response advertises `batch-sprint`; it must be a real, inspectable ref,
    # not a name for a branch that was assembled and immediately discarded.
    assert resp["batch"] == "batch-sprint"
    assert _branch_exists(repo, "batch-sprint")
    # The throwaway assembly worktree is still cleaned up — only the branch stays.
    wt_list = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        capture_output=True,
        encoding="utf-8",
    ).stdout
    assert wt_list.count("worktree ") == 1  # only the main checkout remains
