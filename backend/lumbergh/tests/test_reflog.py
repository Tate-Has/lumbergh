"""The reflog — where a commit goes when the graph stops showing it."""

import subprocess
from pathlib import Path

import pytest

from lumbergh.git_utils import get_reflog


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "work"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    for n in range(1, 4):
        (repo / f"f{n}.txt").write_text(f"{n}\n")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", f"commit {n}")
    return repo


def test_lists_head_movements_newest_first(repo):
    entries = get_reflog(repo)

    assert [e["message"] for e in entries][:3] == [
        "commit: commit 3",
        "commit: commit 2",
        "commit (initial): commit 1",
    ]
    assert entries[0]["selector"] == "HEAD@{0}"
    assert len(entries[0]["hash"]) == 40
    assert entries[0]["shortHash"] == entries[0]["hash"][:7]


def test_keeps_the_commit_a_hard_reset_threw_away(repo):
    lost = git(repo, "rev-parse", "HEAD")
    git(repo, "reset", "--hard", "-q", "HEAD~2")

    entries = get_reflog(repo)

    assert git(repo, "log", "--format=%H").count(lost) == 0, "gone from the graph"
    assert any(e["hash"] == lost for e in entries), "still reachable from the reflog"
    assert entries[0]["message"].startswith("reset:")


def test_says_who_moved_and_when(repo):
    entry = get_reflog(repo)[0]

    assert entry["relativeDate"]
    assert entry["action"] == "commit"


def test_the_action_is_the_verb_alone(repo):
    """git writes "merge <branch>: ..." — the branch belongs in the message."""
    git(repo, "checkout", "-qb", "side")
    (repo / "side.txt").write_text("side\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "side work")
    git(repo, "checkout", "-q", "master") if "master" in git(repo, "branch") else git(
        repo, "checkout", "-q", "main"
    )
    git(repo, "merge", "-q", "side")

    merge = get_reflog(repo)[0]

    assert merge["action"] == "merge"
    assert "side" in merge["message"]


def test_the_action_ignores_gits_parenthetical(repo):
    """ "commit (initial)" and "commit (amend)" are both a commit."""
    initial = get_reflog(repo)[-1]

    assert initial["message"] == "commit (initial): commit 1"
    assert initial["action"] == "commit"


def test_a_limit_is_respected(repo):
    assert len(get_reflog(repo, limit=2)) == 2


def test_a_repo_without_git_is_an_error_not_a_crash(tmp_path):
    result = get_reflog(tmp_path / "nope")

    assert result == []
