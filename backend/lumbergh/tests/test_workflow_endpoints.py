import pytest
from fastapi import HTTPException

from lumbergh.routers import bill


def test_batch_spawns_one_worker_per_brief(monkeypatch, tmp_path):
    d = tmp_path / "briefs"
    d.mkdir()
    (d / "kb-1.md").write_text("one")
    (d / "kb-2.md").write_text("two")

    calls = []

    def fake_spawn(body):
        calls.append((body.into, body.run, body.name, body.branch))
        return {
            "session": f"{body.into}:{body.name}",
            "kind": body.kind,
            "branch": body.branch,
            "path": f"/wt/{body.name}",
        }

    monkeypatch.setattr(bill, "spawn", fake_spawn)

    resp = bill.batch(
        bill.BatchBody(repo=str(tmp_path / "repo"), run="sprint", briefs=[str(d)], kind="ship")
    )
    assert resp["session"] == "sprint"
    assert {c[2] for c in calls} == {"kb-1", "kb-2"}
    assert all(c[0] == "sprint" and c[1] == "sprint" for c in calls)
    assert len(resp["workers"]) == 2
    assert resp["failed"] == []


def test_batch_records_a_failed_brief_without_aborting(monkeypatch, tmp_path):
    d = tmp_path / "briefs"
    d.mkdir()
    (d / "ok.md").write_text("ok")
    (d / "bad.md").write_text("bad")

    def fake_spawn(body):
        if body.name == "bad":
            raise HTTPException(status_code=400, detail={"stage": "worktree", "error": "boom"})
        return {
            "session": f"{body.into}:{body.name}",
            "kind": body.kind,
            "branch": body.branch,
            "path": "/wt/ok",
        }

    monkeypatch.setattr(bill, "spawn", fake_spawn)
    resp = bill.batch(bill.BatchBody(repo=str(tmp_path), run="r", briefs=[str(d)], kind="ship"))
    assert len(resp["workers"]) == 1
    assert resp["failed"] == [{"brief": "bad", "error": {"stage": "worktree", "error": "boom"}}]


def test_land_without_push_assembles_smokes_and_stops(monkeypatch):
    monkeypatch.setattr(
        "lumbergh.routers.bill.run_members",
        lambda _r: [
            {"parent_repo": "/repo/port", "branch": "feat-a", "target": "sprint:feat-a"},
            {"parent_repo": "/repo/port", "branch": "feat-b", "target": "sprint:feat-b"},
        ],
    )
    monkeypatch.setattr("lumbergh.routers.bill.land.branch_exists", lambda *_a: True)
    monkeypatch.setattr(
        "lumbergh.routers.bill.land.prepare_deps", lambda *_a: {"ok": True, "resynced": []}
    )
    monkeypatch.setattr(
        "lumbergh.routers.bill.land.assemble",
        lambda _repo, run, _base, _branches: {
            "ok": True,
            "worktree": "assembly-dir",
            "batch": f"batch-{run}",
            "picked": {},
        },
    )
    smoked = {}
    monkeypatch.setattr(
        "lumbergh.routers.bill.land.run_smoke",
        lambda _wt, cmd: (smoked.setdefault("cmd", cmd), {"ok": True, "returncode": 0})[1],
    )
    monkeypatch.setattr(
        "lumbergh.routers.bill.worktrees.read_land_smoke", lambda _repo: "make test"
    )
    pushed = {}
    monkeypatch.setattr(
        "lumbergh.routers.bill.land.push_batch", lambda *_a: pushed.setdefault("did", True)
    )
    monkeypatch.setattr("lumbergh.routers.bill.land.cleanup_assembly", lambda *_a: None)

    resp = bill.land_run(bill.LandBody(run="sprint", onto="master", push=False))
    assert resp["pushed"] is False
    assert smoked["cmd"] == "make test"
    assert "did" not in pushed


def test_land_empty_run_fails(monkeypatch):
    monkeypatch.setattr("lumbergh.routers.bill.run_members", lambda _r: [])
    with pytest.raises(HTTPException):
        bill.land_run(bill.LandBody(run="nope"))


def test_teardown_kills_windows_and_reaps_members(monkeypatch):
    monkeypatch.setattr(
        "lumbergh.routers.bill.run_members",
        lambda _r: [
            {"target": "sprint:a", "path": "/wt/a"},
            {"target": "sprint:b", "path": "/wt/b"},
        ],
    )
    killed = []
    monkeypatch.setattr(
        "lumbergh.routers.bill.kill_tmux_window", lambda t: killed.append(t) or True
    )

    def fake_reap(path, **_kwargs):
        return (
            {"status": "removed"} if "a" in str(path) else {"status": "refused", "reason": "dirty"}
        )

    monkeypatch.setattr("lumbergh.routers.bill.worktrees.reap", fake_reap)

    resp = bill.teardown(bill.TeardownBody(run="sprint"))
    assert set(killed) == {"sprint:a", "sprint:b"}
    assert resp["refused"] == [{"target": "sprint:b", "reason": "dirty"}]
