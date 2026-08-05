"""`lb land --push` must land the tree that was gated, not a re-assembly of whatever
the worker branches say now.

The reported sequence: six of seven workers deliver, the overseer assembles and gates the
six, the seventh commits between the gate and the `--push`, and `--push` rebuilds from the
worker branches — silently landing a commit no gate ever ran on.
"""

import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from lumbergh.routers import bill


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo, name, text):
    (repo / name).write_text(text)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", f"{name}:{text}")


@pytest.fixture
def run_of_two(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "dev")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _commit(repo, "base.txt", "base")
    origin = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", "-q", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "-q", "origin")
    for name in ("feat-a", "feat-b"):
        _git(repo, "checkout", "-q", "-b", name, "dev")
        _commit(repo, f"{name}.txt", name)
    _git(repo, "checkout", "-q", "dev")

    monkeypatch.setattr(
        bill,
        "run_members",
        lambda _r: [
            {"parent_repo": str(repo), "branch": "feat-a", "target": "sprint:feat-a"},
            {"parent_repo": str(repo), "branch": "feat-b", "target": "sprint:feat-b"},
        ],
    )
    return repo


def test_push_refuses_when_a_worker_committed_after_the_gate(run_of_two):
    repo = run_of_two
    assembled = bill.land_run(bill.LandBody(run="sprint", onto="dev", skip_smoke=True))
    assert assembled["pushed"] is False
    gated = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "batch-sprint"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()

    _git(repo, "checkout", "-q", "feat-b")
    _commit(repo, "feat-b.txt", "late work the gate never saw")
    _git(repo, "checkout", "-q", "dev")

    with pytest.raises(HTTPException) as raised:
        bill.land_run(bill.LandBody(run="sprint", onto="dev", push=True, skip_smoke=True))
    detail = raised.value.detail
    assert detail["stage"] == "stale"
    assert "feat-b" in detail["error"]

    # Nothing landed, and the gated batch is still there to re-inspect.
    on_remote = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "origin/dev"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()
    assert on_remote != gated
    assert Path(repo / ".git").exists()


def test_push_lands_the_assembled_batch_when_no_worker_moved(run_of_two):
    repo = run_of_two
    bill.land_run(bill.LandBody(run="sprint", onto="dev", skip_smoke=True))
    gated = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "batch-sprint"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()

    resp = bill.land_run(bill.LandBody(run="sprint", onto="dev", push=True, skip_smoke=True))
    assert resp["pushed"] is True
    assert resp["sha"] == gated
    landed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "origin/dev"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()
    assert landed == gated
