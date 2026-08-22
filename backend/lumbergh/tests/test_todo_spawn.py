"""Launching a todo as a worker: the todo becomes a brief, the brief becomes a spawn.

The composition is what these cover — which repo the worktree branches from, what the
brief says, and what branch name the todo's text turns into. The spawn itself is Bill's
and already tested; here it is a spy.
"""

import pytest
from fastapi import HTTPException

from lumbergh import todo_spawn


def _repo(tmp_path, name="repo"):
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True)
    return repo


def test_a_plain_session_launches_from_its_own_workdir(tmp_path):
    repo = _repo(tmp_path)

    assert todo_spawn.launch_repo({"workdir": str(repo)}) == repo


def test_a_worker_launches_from_the_repo_it_branched_from(tmp_path):
    """One tier: launching from a worker gives the main repo a sibling, not a grandchild."""
    repo = _repo(tmp_path)
    meta = {
        "workdir": str(tmp_path / "repo-worktrees" / "port-644"),
        "worktree_parent_repo": str(repo),
    }

    assert todo_spawn.launch_repo(meta) == repo


def test_a_session_with_nowhere_to_branch_from_is_refused():
    with pytest.raises(HTTPException) as e:
        todo_spawn.launch_repo({})

    assert e.value.status_code == 400
    assert e.value.detail["stage"] == "repo"


def test_branch_is_a_slug_of_the_todo_text():
    assert (
        todo_spawn.branch_for("Fix the stale dist bundle!", taken=set())
        == "fix-the-stale-dist-bundle"
    )


def test_branch_stays_short_enough_to_read():
    branch = todo_spawn.branch_for(
        "Make the idle detector stop reading a repaint as work when a viewer attaches",
        taken=set(),
    )

    assert len(branch) <= todo_spawn.MAX_BRANCH_LEN
    assert not branch.endswith("-")


def test_branch_sidesteps_names_already_in_use():
    assert todo_spawn.branch_for("Fix the graph", taken={"fix-the-graph"}) == "fix-the-graph-2"
    assert (
        todo_spawn.branch_for("Fix the graph", taken={"fix-the-graph", "fix-the-graph-2"})
        == "fix-the-graph-3"
    )


def test_a_todo_with_no_usable_characters_still_gets_a_branch():
    assert todo_spawn.branch_for("!!!", taken=set()) == "todo"


def test_brief_carries_the_todo_text_and_description(tmp_path, monkeypatch):
    monkeypatch.setattr(todo_spawn.bill_bundle, "home", lambda: tmp_path)

    brief = todo_spawn.write_brief("Fix the graph", "It double-counts merges.", "fix-the-graph")

    assert brief == tmp_path / "briefs" / "fix-the-graph.md"
    body = brief.read_text()
    assert "Fix the graph" in body
    assert "It double-counts merges." in body


def test_brief_of_a_bare_todo_is_just_the_task(tmp_path, monkeypatch):
    monkeypatch.setattr(todo_spawn.bill_bundle, "home", lambda: tmp_path)

    body = todo_spawn.write_brief("Fix the graph", "", "fix-the-graph").read_text()

    assert body.strip() == "# Fix the graph"


def test_launch_spawns_a_ship_worker_on_a_new_branch(tmp_path, monkeypatch):
    monkeypatch.setattr(todo_spawn.bill_bundle, "home", lambda: tmp_path)
    seen = {}

    def spy(body):
        seen["body"] = body
        return {"session": "fix-the-graph", "path": str(tmp_path / "wt"), "branch": body.branch}

    repo = _repo(tmp_path)
    result = todo_spawn.launch(
        {"workdir": str(repo)},
        {"text": "Fix the graph", "description": "It double-counts merges."},
        taken=set(),
        spawn=spy,
    )

    body = seen["body"]
    assert body.repo == str(repo)
    assert body.branch == "fix-the-graph"
    assert body.kind == "ship"
    assert body.create_branch is True
    assert body.task_intent == "Fix the graph"
    assert body.brief_path == str(tmp_path / "briefs" / "fix-the-graph.md")
    assert result["session"] == "fix-the-graph"


def test_endpoint_refuses_a_todo_index_that_is_not_there(tmp_path, monkeypatch):
    from tinydb import TinyDB

    from lumbergh.routers import sessions

    repo = _repo(tmp_path)
    monkeypatch.setattr(sessions, "get_session_workdir", lambda _name: repo)
    monkeypatch.setattr(sessions, "get_project_db", lambda _path: TinyDB(tmp_path / "p.json"))

    with pytest.raises(HTTPException) as e:
        sessions.launch_session_todo("port", 0)

    assert e.value.status_code == 400
    assert "index" in str(e.value.detail)


def test_endpoint_launches_the_todo_at_that_index(tmp_path, monkeypatch):
    from tinydb import TinyDB

    from lumbergh.routers import sessions

    repo = _repo(tmp_path)
    db = TinyDB(tmp_path / "p.json")
    db.table("todos").insert({"items": [{"text": "first"}, {"text": "second"}]})
    monkeypatch.setattr(sessions, "get_session_workdir", lambda _name: repo)
    monkeypatch.setattr(sessions, "get_project_db", lambda _path: db)
    monkeypatch.setattr(sessions, "get_stored_sessions", lambda: {"port": {"workdir": str(repo)}})
    monkeypatch.setattr(sessions, "get_live_sessions", lambda: {"port": {}})
    monkeypatch.setattr(sessions.worktrees, "all_entries", lambda: [{"branch": "second"}])
    monkeypatch.setattr(todo_spawn.bill_bundle, "home", lambda: tmp_path)
    seen = {}
    monkeypatch.setattr(
        "lumbergh.routers.bill.spawn", lambda body: (seen.setdefault("body", body) and None) or {}
    )

    sessions.launch_session_todo("port", 1)

    assert seen["body"].task_intent == "second"
    assert seen["body"].branch == "second-2", "a branch already in use must be sidestepped"
