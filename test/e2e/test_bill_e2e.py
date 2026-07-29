"""E2E for Bill's control surface: summon -> fleet -> spawn guard -> spawn -> reap.

The client only ever sends path strings; all filesystem and git work happens
server-side, exactly like ``test_worktrees_e2e.py``. That is what lets these tests
run unmodified whether pytest talks to a local dev server or, under
``test/e2e-vm.sh``, to a server living inside a QEMU VM while pytest stays on the
host — there is no filesystem shared between the two to cheat with.

Two environment traps shape these tests, and both make summon *refuse* rather than
misbehave — so no test here may assume summon succeeds:

* ``/api/bill/summon`` verifies that a live session named ``bill`` really is Bill
  (its recorded workdir must resolve to Bill's home) before reporting it as
  "existing". On a developer's own machine, a session named ``bill`` may already
  exist for an unrelated reason (e.g. a worktree session), in which case summon
  refuses with ``stage="identity"``.
* Summon hardcodes the ``pi`` provider with no override, and it checks that the
  harness binary is installed before creating a session — a session whose pane
  command dies immediately is worse than a refusal, because it looks live. ``pi``
  is not installed in the e2e VM, so there summon refuses with ``stage="harness"``.

Either refusal is a legitimate outcome of a healthy server, so every test that
branches on the failure accepts both stages. Both carry ``workdir``, because Bill's
home is materialized before either check runs and a caller that only needs the path
must still get it.

The spawn roundtrip sidesteps the missing-``pi`` problem on the worker side by
requesting ``claude-code`` instead, matching the pattern already used in
``test_session_lifecycle.py``.
"""

import uuid
from pathlib import Path

REFUSAL_STAGES = {"identity", "harness"}


def test_summon_is_idempotent_whichever_branch_the_environment_routes_it_into(client):
    """A second summon call must land in the same branch as the first.

    Covers a truly fresh Bill, a name already held by a foreign session (a developer
    host where ``bill`` means something else), and a host with no ``pi`` installed (the
    VM) without the test needing to know in advance which world it's running in — and
    a refusal must be as stable across calls as a success is.
    """
    created_here = False
    try:
        first = client.post("/api/bill/summon")
        if first.status_code == 200:
            body = first.json()
            assert body["session"] == "bill"
            assert body["workdir"].endswith("/bill")
            created_here = body["existing"] is False

            second = client.post("/api/bill/summon")
            assert second.status_code == 200, second.text
            assert second.json() == {
                "session": "bill",
                "workdir": body["workdir"],
                "existing": True,
            }
        else:
            assert first.status_code == 400, first.text
            detail = first.json()["detail"]
            assert detail["stage"] in REFUSAL_STAGES, detail
            assert detail["workdir"].endswith("/bill")

            second = client.post("/api/bill/summon")
            assert second.status_code == 400
            assert second.json()["detail"]["stage"] == detail["stage"]
    finally:
        if created_here:
            client.delete("/api/sessions/bill")


def test_fleet_total_matches_the_task_list_it_reports(client):
    body = client.get("/api/bill/fleet").json()
    assert body["total"] == len(body["tasks"])
    assert all("session" in row and "kind" in row for row in body["tasks"])


def test_fleet_wait_times_out_when_nothing_needs_attention(client):
    """A calm fleet times out rather than waking, and says so.

    ``waited`` is bounded below by the requested timeout and above by one poll interval
    past it — the loop only notices the deadline when it next wakes — so this asserts a
    range rather than a point. The server's poll interval is deliberately human-scale,
    hence the generous ceiling.
    """
    timeout = 2
    origin = f"e2e-nobody-{uuid.uuid4().hex[:8]}"
    body = client.get("/api/bill/fleet/wait", params={"timeout": timeout, "origin": origin}).json()
    assert body["woke"] is False
    assert body["total"] == 0
    assert body["tasks"] == []
    assert timeout <= body["waited"] <= timeout + 5


def test_spawn_refuses_a_brief_the_server_cannot_read(client, test_repo_dir):
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": test_repo_dir,
            "branch": f"e2e/bill-{uuid.uuid4().hex[:8]}",
            "kind": "ship",
            "brief_path": "/nonexistent/brief.md",
            "create_branch": True,
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "brief"


def test_spawn_refuses_an_unknown_kind(client, test_repo_dir):
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": test_repo_dir,
            "branch": f"e2e/bill-{uuid.uuid4().hex[:8]}",
            "kind": "wander",
            "brief_path": "/nonexistent/brief.md",
            "create_branch": True,
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "kind"


def _bills_home(client) -> str:
    """Bill's home directory, learned from summon whichever branch it takes.

    ``materialize()`` runs unconditionally at the top of ``/api/bill/summon``, before
    both the identity check and the harness check, so his home exists and its path is
    known even when the summon is refused — every refusal carries ``workdir`` for
    exactly this reason, and the tests below depend on all of them doing so.
    """
    r = client.post("/api/bill/summon")
    if r.status_code == 200:
        return r.json()["workdir"]
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert detail["stage"] in REFUSAL_STAGES, detail
    assert "workdir" in detail, f"a {detail['stage']} refusal must still report Bill's home"
    return detail["workdir"]


def test_spawn_then_fleet_then_reap_roundtrip(client, test_repo_dir):
    """Spawns the way AGENTS.md tells Bill to: a ``--brief`` relative to his home.

    Bill's cwd is his home, so that is the form the real system uses. Passing an
    absolute path here (as this test used to) would leave the documented invocation
    untested end to end.
    """
    home = _bills_home(client)
    branch = f"e2e/bill-{uuid.uuid4().hex[:8]}"
    name = f"e2e-bill-{uuid.uuid4().hex[:6]}"
    brief_path = f"{home}/briefs/{name}.md"
    created_path = None

    written = client.post(
        "/api/bill/brief",
        json={"path": brief_path, "body": "# Task: e2e smoke\n\nDo nothing.\n"},
    )
    assert written.status_code == 200, written.text

    try:
        r = client.post(
            "/api/bill/spawn",
            json={
                "repo": test_repo_dir,
                "branch": branch,
                "kind": "scout",
                "brief_path": f"briefs/{name}.md",
                "name": name,
                "create_branch": True,
                "agent_provider": "claude-code",
            },
        )
        assert r.status_code == 200, r.text
        created_path = r.json()["path"]
        assert r.json()["session"] == name
        assert r.json()["brief_path"] == brief_path, "a relative --brief must resolve to his home"

        tasks = client.get("/api/bill/fleet", params={"origin": "bill"}).json()["tasks"]
        row = next((t for t in tasks if t["task"] == name), None)
        assert row is not None, f"spawned task missing from fleet: {tasks}"
        assert row["kind"] == "scout"
        # Bill has no other source for these; without them on the row he invents them.
        # The fleet row's path is resolved server-side (see test_worktrees_e2e.py),
        # while created_path is the unresolved string worktrees.create returned, so
        # compare them as paths rather than strings — a symlinked test dir would
        # otherwise make this assertion fail even though nothing is wrong.
        assert Path(row["path"]) == Path(created_path).resolve()
        assert row["repo_path"].startswith("/")
        assert row["repo_path"].endswith(test_repo_dir.rstrip("/").rsplit("/", 1)[-1])
    finally:
        client.delete(f"/api/sessions/{name}")
        if created_path:
            client.post(
                "/api/worktrees/reap",
                json={"path": created_path, "force": True, "rm_branch": True},
            )


def test_brief_endpoint_refuses_a_path_outside_bills_home(client):
    r = client.post(
        "/api/bill/brief",
        json={"path": "/tmp/definitely-not-bills-home/escape.md", "body": "x"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "path"
