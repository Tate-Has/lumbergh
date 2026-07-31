from lumbergh.runs import run_members


def test_run_members_filters_by_run_id_sorted_by_target(monkeypatch):
    monkeypatch.setattr(
        "lumbergh.worktrees.all_entries",
        lambda: [
            {"target": "s:b", "run": "r1", "branch": "b"},
            {"target": "s:a", "run": "r1", "branch": "a"},
            {"target": "solo", "run": None, "branch": "x"},
            {"target": "s:c", "run": "r2", "branch": "c"},
        ],
    )
    members = run_members("r1")
    assert [m["target"] for m in members] == ["s:a", "s:b"]


def test_run_members_empty_for_unknown_run(monkeypatch):
    monkeypatch.setattr("lumbergh.worktrees.all_entries", list)
    assert run_members("nope") == []
