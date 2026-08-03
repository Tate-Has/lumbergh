import subprocess

import pytest
from fastapi import HTTPException

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


def test_land_refuses_when_a_members_branch_cannot_be_resolved(monkeypatch, repo_with_run):
    """A member whose branch name doesn't resolve contributed zero commits, and the
    land output was byte-identical to a complete one. Silence is the bug: refuse,
    and name the worker."""
    repo = repo_with_run
    members = [
        {"target": "sprint:feat-a", "branch": "feat-a", "parent_repo": str(repo), "run": "sprint"},
        {
            "target": "sprint:issue-710",
            "branch": "710",  # spawned as `--branch 710`, the branch is `issue-710`
            "parent_repo": str(repo),
            "run": "sprint",
        },
    ]
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: members)

    with pytest.raises(HTTPException) as exc:
        bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, skip_smoke=True))

    assert exc.value.detail["stage"] == "members"
    assert "sprint:issue-710" in exc.value.detail["error"]
    assert "710" in exc.value.detail["error"]
    assert not _branch_exists(repo, "batch-sprint")  # nothing half-assembled left behind


def test_land_reports_the_worker_to_commit_mapping_on_push(monkeypatch, repo_with_run):
    """The count has to be verifiable from the land output itself, without git
    archaeology — on the --push path as much as the assembly path."""
    repo = repo_with_run
    members = [
        {"target": "sprint:feat-a", "branch": "feat-a", "parent_repo": str(repo), "run": "sprint"},
        {"target": "sprint:feat-b", "branch": "feat-b", "parent_repo": str(repo), "run": "sprint"},
    ]
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: members)

    bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, skip_smoke=True))
    resp = bill.land_run(bill.LandBody(run="sprint", onto="master", push=True, skip_smoke=True))

    assert set(resp["picked"]) == {"feat-a", "feat-b"}
    assert all(len(shas) == 1 for shas in resp["picked"].values())


def test_teardown_reports_whether_each_worker_landed(monkeypatch, tmp_path):
    """Teardown is the only thing that knows a run was torn down *without* landing.
    It stays repo-agnostic — it exposes the fact and leaves board semantics alone."""
    members = [
        {
            "target": "sprint:landed",
            "branch": "landed",
            "parent_repo": str(tmp_path),
            "path": str(tmp_path / "wt-landed"),
            "run": "sprint",
        },
        {
            "target": "sprint:abandoned",
            "branch": "abandoned",
            "parent_repo": str(tmp_path),
            "path": str(tmp_path / "wt-abandoned"),
            "run": "sprint",
        },
    ]
    monkeypatch.setattr("lumbergh.routers.bill.run_members", lambda _run: members)
    monkeypatch.setattr(
        "lumbergh.worktrees.reap",
        lambda p, **_k: {"status": "removed", "landed": "landed" in str(p)},
    )
    monkeypatch.setattr("lumbergh.land.delete_batch", lambda *_a: True)
    monkeypatch.setattr("lumbergh.routers.bill.kill_tmux_window", lambda _t: True)

    resp = bill.teardown(bill.TeardownBody(run="sprint", force=True))

    by_target = {r["target"]: r for r in resp["results"]}
    assert by_target["sprint:landed"]["landed"] is True
    assert by_target["sprint:abandoned"]["landed"] is False


def test_teardown_dry_run_reports_the_verdict_without_touching_anything(monkeypatch, tmp_path):
    """The point of a dry run is to see what a teardown would decide *before* any
    window is killed or any worktree removed."""
    members = [
        {
            "target": "sprint:issue-749",
            "branch": "issue-749",
            "parent_repo": str(tmp_path),
            "path": str(tmp_path / "wt"),
            "run": "sprint",
        }
    ]
    monkeypatch.setattr("lumbergh.routers.bill.run_members", lambda _run: members)
    monkeypatch.setattr(
        "lumbergh.worktrees.reap_readiness",
        lambda _p: {"landed": True, "commits": 2, "blocker": None},
    )

    def _no_destruction(*_a, **_k):
        raise AssertionError("a dry run must not kill or reap anything")

    monkeypatch.setattr("lumbergh.worktrees.reap", _no_destruction)
    monkeypatch.setattr("lumbergh.routers.bill.kill_tmux_window", _no_destruction)
    monkeypatch.setattr("lumbergh.land.delete_batch", _no_destruction)

    resp = bill.teardown(bill.TeardownBody(run="sprint", dry_run=True))

    assert resp["dry_run"] is True
    assert resp["results"] == [
        {
            "target": "sprint:issue-749",
            "killed": False,
            "reaped": "dry-run",
            "landed": True,
            "commits": 2,
        }
    ]
    assert resp["refused"] == []


def test_teardown_reports_the_commit_count_alongside_landed(monkeypatch, tmp_path):
    """`landed: false` with zero commits is a scout that landed nothing, not work that
    was lost — the consumer resetting tracking issues has to tell those apart."""
    members = [
        {
            "target": "sprint:scout-585",
            "branch": "scout-585",
            "parent_repo": str(tmp_path),
            "path": str(tmp_path / "wt"),
            "run": "sprint",
        }
    ]
    monkeypatch.setattr("lumbergh.routers.bill.run_members", lambda _run: members)
    monkeypatch.setattr(
        "lumbergh.worktrees.reap",
        lambda _p, **_k: {"status": "removed", "landed": False, "commits": 0},
    )
    monkeypatch.setattr("lumbergh.land.delete_batch", lambda *_a: True)
    monkeypatch.setattr("lumbergh.routers.bill.kill_tmux_window", lambda _t: True)

    resp = bill.teardown(bill.TeardownBody(run="sprint"))

    assert resp["results"][0]["commits"] == 0
    assert resp["results"][0]["landed"] is False


def test_teardown_refusal_names_its_reason(monkeypatch, tmp_path):
    """`--force` stops being read the moment every refusal looks the same. A refusal
    must say which of the two things it is."""
    members = [
        {
            "target": "sprint:dirty",
            "branch": "dirty",
            "parent_repo": str(tmp_path),
            "path": str(tmp_path / "wt"),
            "run": "sprint",
        }
    ]
    monkeypatch.setattr("lumbergh.routers.bill.run_members", lambda _run: members)
    monkeypatch.setattr(
        "lumbergh.worktrees.reap",
        lambda _p, **_k: {"error": "worktree has uncommitted changes", "reason": "dirty"},
    )
    monkeypatch.setattr("lumbergh.land.delete_batch", lambda *_a: True)
    monkeypatch.setattr("lumbergh.routers.bill.kill_tmux_window", lambda _t: True)

    resp = bill.teardown(bill.TeardownBody(run="sprint"))

    assert resp["refused"] == [{"target": "sprint:dirty", "reason": "dirty"}]


def test_push_lands_commits_added_to_the_assembled_batch_branch(monkeypatch, repo_with_run):
    repo = repo_with_run
    origin = repo.parent / "origin.git"
    members = [
        {"target": "sprint:feat-a", "branch": "feat-a", "parent_repo": str(repo), "run": "sprint"},
        {"target": "sprint:feat-b", "branch": "feat-b", "parent_repo": str(repo), "run": "sprint"},
    ]
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: members)

    # Step 1: assemble (no push) — leaves batch-sprint in place for inspection.
    bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, skip_smoke=True))

    # Step 2: add a commit to the assembled batch branch — a config fix that belongs
    # with this batch, exactly as the `next:` message invites ("inspect it, then --push").
    wt = repo.parent / "inspect-wt"
    _git(repo, "worktree", "add", "-q", str(wt), "batch-sprint")
    (wt / "config-fix.txt").write_text("belongs with this batch")
    _git(wt, "add", ".")
    _git(wt, "commit", "-qm", "chore: config fix that belongs with the batch")
    _git(repo, "worktree", "remove", "--force", str(wt))

    # Step 3: push. The tree that gets landed must be the branch we inspected — the
    # manually-added commit must not be silently discarded by a re-assembly.
    resp = bill.land_run(bill.LandBody(run="sprint", onto="master", push=True, skip_smoke=True))
    assert resp["pushed"] is True

    landed = subprocess.run(
        ["git", "-C", str(origin), "log", "--format=%s", "master"],
        capture_output=True,
        encoding="utf-8",
    ).stdout
    assert "chore: config fix that belongs with the batch" in landed


def test_push_refuses_when_a_worker_moved_after_assembly(monkeypatch, repo_with_run):
    repo = repo_with_run
    origin = repo.parent / "origin.git"
    members = [
        {"target": "sprint:feat-a", "branch": "feat-a", "parent_repo": str(repo), "run": "sprint"},
        {"target": "sprint:feat-b", "branch": "feat-b", "parent_repo": str(repo), "run": "sprint"},
    ]
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: members)

    bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, skip_smoke=True))

    # A worker gains a new commit after the batch was assembled — a normal step when
    # an overseer nudges it to fix a review finding. The stale batch must not land.
    wt = repo.parent / "worker-wt"
    _git(repo, "worktree", "add", "-q", str(wt), "feat-a")
    (wt / "feat-a.txt").write_text("feat-a revised after review")
    _git(wt, "add", ".")
    _git(wt, "commit", "-qm", "fix: address review on feat-a")
    _git(repo, "worktree", "remove", "--force", str(wt))

    with pytest.raises(HTTPException) as exc:
        bill.land_run(bill.LandBody(run="sprint", onto="master", push=True, skip_smoke=True))
    assert exc.value.detail["stage"] == "stale"
    assert "feat-a" in exc.value.detail["error"]

    landed = subprocess.run(
        ["git", "-C", str(origin), "log", "--format=%s", "master"],
        capture_output=True,
        encoding="utf-8",
    ).stdout
    assert landed.strip() == "base"  # nothing was pushed


def test_push_reports_the_landed_sha(monkeypatch, repo_with_run):
    repo = repo_with_run
    members = [
        {"target": "sprint:feat-a", "branch": "feat-a", "parent_repo": str(repo), "run": "sprint"},
    ]
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: members)

    bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, skip_smoke=True))
    batch_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "batch-sprint"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()

    resp = bill.land_run(bill.LandBody(run="sprint", onto="master", push=True, skip_smoke=True))
    assert resp["sha"] == batch_sha  # the response names exactly what was landed


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
