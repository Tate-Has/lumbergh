import subprocess
from pathlib import Path

from lumbergh.git_utils import get_graph_log


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "t")
    (path / "README").write_text("x")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    return path


def test_graph_without_worktrees_lists_only_main(tmp_path):
    repo = _init_repo(tmp_path / "repo")

    graph = get_graph_log(repo)

    assert [wt["branch"] for wt in graph["worktrees"]] != []
    main = next(wt for wt in graph["worktrees"] if wt["isMain"])
    assert main["isCurrent"] is True
    assert main["sessionName"] is None
    assert len(graph["worktrees"]) == 1


def test_graph_annotates_sibling_worktree(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    wt_path = tmp_path / "repo-wt"
    _git(repo, "worktree", "add", "-q", "-b", "feature/foo", str(wt_path))

    graph = get_graph_log(repo)

    short_hashes = {c["hash"][:7] for c in graph["commits"]}
    sibling = next(wt for wt in graph["worktrees"] if not wt["isMain"])
    assert sibling["branch"] == "feature/foo"
    assert sibling["headHash"] in short_hashes
    assert sibling["isCurrent"] is False
    assert sibling["sessionName"] is None

    main = next(wt for wt in graph["worktrees"] if wt["isMain"])
    assert main["isCurrent"] is True


def test_graph_resolves_session_name_from_path_map(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    wt_path = tmp_path / "repo-wt"
    _git(repo, "worktree", "add", "-q", "-b", "feature/foo", str(wt_path))

    session_paths = {str(wt_path.resolve()): "foo-worker"}
    graph = get_graph_log(repo, session_paths=session_paths)

    sibling = next(wt for wt in graph["worktrees"] if not wt["isMain"])
    assert sibling["sessionName"] == "foo-worker"


def test_session_path_map_resolves_workdir_to_name(tmp_path, monkeypatch):
    from lumbergh.routers import sessions

    wt_path = tmp_path / "wt"
    wt_path.mkdir()
    monkeypatch.setattr(
        sessions,
        "get_stored_sessions",
        lambda: {"foo-worker": {"workdir": str(wt_path)}, "no-dir": {}},
    )

    path_map = sessions.get_session_path_map()

    assert path_map == {str(wt_path.resolve()): "foo-worker"}


def test_a_diverged_remote_branch_is_labelled_with_its_remote(tmp_path):
    """Local `dev` and `origin/dev` at different commits both read as "dev",
    which looks like the branch head failed to update."""
    origin = _init_repo(tmp_path / "origin")
    _git(origin, "branch", "dev")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(clone, "config", "user.email", "t@t.t")
    _git(clone, "config", "user.name", "t")
    _git(clone, "checkout", "-q", "dev")
    (clone / "NEW").write_text("y")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-qm", "local work")

    graph = get_graph_log(clone)
    names = [ref["name"] for commit in graph["commits"] for ref in commit["refs"]]

    assert "dev" in names
    assert "origin/dev" in names
    assert names.count("dev") == 1
