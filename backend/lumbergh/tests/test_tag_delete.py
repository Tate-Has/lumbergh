"""Deleting a tag, locally and on the remote."""

import subprocess
from pathlib import Path

import pytest

from lumbergh.git_utils import delete_tag, list_remote_tags


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo_with_remote(tmp_path):
    """A repo with one tag pushed to a bare 'origin' and one kept local."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)

    repo = tmp_path / "work"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("# tags\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "initial")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "tag", "v1.0.0")
    git(repo, "tag", "local-only")
    git(repo, "push", "-q", "origin", "HEAD", "v1.0.0")
    return repo


def local_tags(repo: Path) -> list[str]:
    return git(repo, "tag", "--list").splitlines()


def test_lists_only_the_tags_the_remote_has(repo_with_remote):
    assert list_remote_tags(repo_with_remote) == ["v1.0.0"]


def test_deletes_a_local_tag(repo_with_remote):
    result = delete_tag(repo_with_remote, "local-only")

    assert result.get("status") == "success"
    assert "local-only" not in local_tags(repo_with_remote)
    assert "v1.0.0" in local_tags(repo_with_remote)


def test_deleting_locally_leaves_the_remote_tag_alone(repo_with_remote):
    delete_tag(repo_with_remote, "v1.0.0")

    assert "v1.0.0" not in local_tags(repo_with_remote)
    assert list_remote_tags(repo_with_remote) == ["v1.0.0"]


def test_deletes_on_the_remote_too_when_asked(repo_with_remote):
    result = delete_tag(repo_with_remote, "v1.0.0", delete_remote=True)

    assert result.get("status") == "success"
    assert "v1.0.0" not in local_tags(repo_with_remote)
    assert list_remote_tags(repo_with_remote) == []


def test_reports_an_unknown_tag_instead_of_pretending(repo_with_remote):
    assert "error" in delete_tag(repo_with_remote, "v9.9.9")


def test_remote_tags_are_empty_without_a_remote(tmp_path):
    repo = tmp_path / "solo"
    repo.mkdir()
    git(repo, "init", "-q")

    assert list_remote_tags(repo) == []
