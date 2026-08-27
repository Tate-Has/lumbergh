"""Searching commit history beyond the window the graph has loaded."""

import subprocess

import pytest

from lumbergh.git_utils import search_commits


def commit_file(repo, name, message, author=None):
    (repo / name).write_text(f"{name}\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    cmd = ["git", "commit", "-m", message]
    if author:
        cmd += ["--author", author]
    subprocess.run(cmd, cwd=repo, capture_output=True)


@pytest.fixture
def repo_with_history(mock_git_repo):
    commit_file(mock_git_repo, "parser.py", "fix the parser")
    commit_file(mock_git_repo, "widget.py", "add a widget", author="Ada Lovelace <ada@example.com>")
    commit_file(mock_git_repo, "docs.md", "docs pass")
    return mock_git_repo


def test_matches_commit_message(repo_with_history):
    results = search_commits(repo_with_history, text="parser")
    assert [c["message"] for c in results] == ["fix the parser"]


def test_message_match_is_case_insensitive(repo_with_history):
    assert search_commits(repo_with_history, text="PARSER")


def test_filters_by_author(repo_with_history):
    results = search_commits(repo_with_history, author="Ada")
    assert [c["message"] for c in results] == ["add a widget"]


def test_filters_by_file_path(repo_with_history):
    results = search_commits(repo_with_history, file="widget.py")
    assert [c["message"] for c in results] == ["add a widget"]


def test_author_and_text_must_both_match(repo_with_history):
    assert search_commits(repo_with_history, text="parser", author="Ada") == []


def test_returns_the_fields_the_graph_renders(repo_with_history):
    result = search_commits(repo_with_history, text="parser")[0]
    assert set(result) >= {"hash", "shortHash", "message", "author", "relativeDate"}
    assert result["shortHash"] == result["hash"][:7]


def test_honours_the_limit(repo_with_history):
    """Three commits are by Test User; the limit must cut the result short."""
    assert len(search_commits(repo_with_history, author="Test User", limit=2)) == 2


def test_empty_search_with_no_criteria_returns_nothing(repo_with_history):
    assert search_commits(repo_with_history) == []


def test_non_git_directory_returns_nothing(tmp_path):
    assert search_commits(tmp_path, text="anything") == []


def test_no_match_returns_empty(repo_with_history):
    assert search_commits(repo_with_history, text="nonexistent-token") == []
