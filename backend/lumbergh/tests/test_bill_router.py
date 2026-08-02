import asyncio
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lumbergh.routers import bill


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(bill.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _no_real_skill_writes(monkeypatch):
    """The spawn path seeds worker skills into real agent dirs (~/.claude, ~/.pi). Stub it
    so tests never touch the user's home; the behavior itself is covered in test_lb_skill."""
    from lumbergh.agent_cli import skill

    monkeypatch.setattr(skill, "ensure_worker_skills", list)


@pytest.fixture(autouse=True)
def _reset_bill_acks():
    """Bill's private ack sets are module globals; clear them so one test's wake can't
    silence the next test's overseer."""
    bill._overseer_acked.clear()
    bill._dead_acked.clear()
    return


def test_fleet_returns_rows(client, monkeypatch):
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "task": "w-a",
                "repo": "app",
                "branch": "feat/a",
                "session": "w-a",
                "kind": "ship",
                "state": "working",
                "since": 5,
                "unseen": False,
                "path": "/w/app-worktrees/feat-a",
            }
        ],
    )
    body = client.get("/api/bill/fleet").json()
    assert body["total"] == 1
    assert body["tasks"][0]["task"] == "w-a"


@pytest.fixture
def fast_poll(monkeypatch):
    """Shrink the (deliberately human-scale) production poll interval.

    Without this, a test that needs N snapshots waits N-1 real poll intervals.
    Tests that pin the *ordering* of the first snapshot must not use this — for
    them the long interval is what makes a premature sleep observable.
    """
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.02)


def test_fleet_wait_checks_the_fleet_before_its_first_sleep(client, monkeypatch):
    """A worker that went blocked before the request arrived must wake it at once.

    Pinned two ways so neither alone can carry it: exactly one snapshot is taken,
    and the call returns far inside one production poll interval — a
    sleep-then-check loop would take ``_POLL_INTERVAL`` seconds to answer.
    """
    calls = {"n": 0}

    def rows(origin, with_outcome=False):  # noqa: ARG001
        calls["n"] += 1
        return [
            {
                "role": "overseer",
                "state": "blocked",
                "unseen": False,
                "task": "port",
                "watched": True,
            }
        ]

    monkeypatch.setattr(bill, "_fleet_rows", rows)
    started = time.monotonic()
    body = client.get("/api/bill/fleet/wait", params={"timeout": 5}).json()
    elapsed = time.monotonic() - started
    assert body["woke"] is True
    assert body["tasks"][0]["task"] == "port"
    assert calls["n"] == 1
    assert elapsed < 0.5
    assert bill._POLL_INTERVAL > 1.0, (
        "the elapsed bound above only means something if a sleep costs more than it"
    )


@pytest.mark.usefixtures("fast_poll")
def test_fleet_wait_times_out_on_a_calm_fleet(client, monkeypatch):
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {"state": "working", "unseen": False, "task": "w-a"}
        ],
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 0.05}).json()
    assert body["woke"] is False
    assert body["total"] == 1


@pytest.mark.usefixtures("fast_poll")
def test_fleet_wait_wakes_when_an_overseer_becomes_blocked(client, monkeypatch):
    calls = {"n": 0}

    def rows(origin, with_outcome=False):  # noqa: ARG001
        calls["n"] += 1
        state = "blocked" if calls["n"] > 2 else "working"
        return [
            {"role": "overseer", "state": state, "unseen": False, "task": "port", "watched": True}
        ]

    monkeypatch.setattr(bill, "_fleet_rows", rows)
    body = client.get("/api/bill/fleet/wait", params={"timeout": 10}).json()
    assert body["woke"] is True
    assert body["tasks"][0]["state"] == "blocked"


def _has_running_loop() -> bool:
    """Whether the *calling thread* is the one running the event loop.

    ``get_running_loop`` raises only when no loop is running in this thread, which is
    exactly the executor-thread case — so this distinguishes "ran on the loop" from
    "ran in the executor" without needing to know either thread's identity (the test
    client's own request thread is a third thread and would confuse an id comparison).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def test_fleet_wait_takes_the_blocking_work_off_the_event_loop(client, monkeypatch):
    """Bill holds this loop open continuously, and each snapshot shells out to tmux and
    to ``git worktree list`` per repo — on the loop that would stall every terminal
    WebSocket at the poll rate. The outcome pass reads transcripts, so it counts too."""
    on_loop = []

    def rows(origin, with_outcome=False):  # noqa: ARG001
        on_loop.append(("snapshot", _has_running_loop()))
        return [
            {
                "role": "overseer",
                "state": "blocked",
                "unseen": False,
                "session": "port",
                "task": "port",
                "watched": True,
            },
            {
                "role": "worker",
                "state": "idle",
                "unseen": False,
                "session": "port-697",
                "task": "port-697",
            },
        ]

    def outcome_of(name):  # noqa: ARG001
        on_loop.append(("outcome", _has_running_loop()))

    monkeypatch.setattr(bill, "_fleet_rows", rows)
    monkeypatch.setattr(bill, "_outcome_of", outcome_of)

    client.get("/api/bill/fleet/wait", params={"timeout": 5})

    assert [step for step, _ in on_loop] == ["snapshot", "outcome"]
    assert not any(ran_on_loop for _, ran_on_loop in on_loop), on_loop


@pytest.mark.usefixtures("fast_poll")
def test_fleet_wait_enriches_worker_outcomes_once_on_the_way_out(client, monkeypatch):
    """The wake is on an overseer, but the payload carries its nested workers with their
    OUTCOME line filled in — so wait must enrich too. Reading transcripts per poll would
    put them back in the hot loop, so this pins that the read happens exactly once, and
    only for the worker (an overseer has no contracted outcome)."""
    calls = {"rows": 0, "outcomes": 0}

    def rows(origin, with_outcome=False):  # noqa: ARG001
        calls["rows"] += 1
        state = "idle" if calls["rows"] > 2 else "working"
        unseen = calls["rows"] > 2
        return [
            {
                "role": "overseer",
                "state": state,
                "unseen": unseen,
                "session": "port",
                "task": "port",
                "watched": True,
            },
            {
                "role": "worker",
                "state": "idle",
                "unseen": False,
                "session": "port-697",
                "task": "port-697",
            },
        ]

    def outcome_of(name):  # noqa: ARG001
        calls["outcomes"] += 1
        return "DELIVERED: https://example.test/pull/7"

    monkeypatch.setattr(bill, "_fleet_rows", rows)
    monkeypatch.setattr(bill, "_outcome_of", outcome_of)

    body = client.get("/api/bill/fleet/wait", params={"timeout": 10}).json()

    worker = next(t for t in body["tasks"] if t["role"] == "worker")
    overseer = next(t for t in body["tasks"] if t["role"] == "overseer")
    assert body["woke"] is True
    assert worker["outcome"] == "DELIVERED: https://example.test/pull/7"
    assert overseer["outcome"] is None  # overseers have no contracted outcome
    assert calls["rows"] == 3
    assert calls["outcomes"] == 1  # only the worker, once


def test_fleet_wait_clamps_an_absurd_timeout(client, monkeypatch):
    """An unbounded timeout would pin a server task (and a worker thread) for as long
    as the caller asked, so the ceiling is the server's, not the caller's."""
    monkeypatch.setattr(bill, "_MAX_WAIT_TIMEOUT", 0.05)
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {"state": "working", "unseen": False, "task": "w-a"}
        ],
    )
    started = time.monotonic()
    body = client.get("/api/bill/fleet/wait", params={"timeout": 100000}).json()
    assert body["woke"] is False
    assert time.monotonic() - started < 5


@pytest.fixture
def attention(monkeypatch):
    """Real attention overlay, reset per test, with persistence stubbed to a no-op
    so tests never touch the user's real config file."""
    from lumbergh import session_attention

    async def _noop():
        return None

    session_attention.reset()
    monkeypatch.setattr(session_attention, "persist", _noop)
    yield session_attention
    session_attention.reset()


def test_overseer_viewing_marks_its_own_workers_seen_but_bill_does_not(
    client, monkeypatch, attention
):
    # A delivered worker sits idle+unseen. It is its overseer's report, not Bill's — so
    # the overseer viewing the fleet clears it, while Bill viewing leaves it alone.
    attention.mark_attention("port-697", "idle")
    assert attention.is_unseen("port-697")
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "worker",
                "task": "port-697",
                "session": "port-697",
                "parent": "port",
                "state": "idle",
                "unseen": True,
            }
        ],
    )
    client.get("/api/bill/fleet", params={"as_session": "bill"})
    assert attention.is_unseen("port-697"), "Bill must not clear a worker's unseen"
    client.get("/api/bill/fleet", params={"as_session": "port"})
    assert not attention.is_unseen("port-697"), "its overseer clears it"


def test_fleet_wait_acks_a_done_unseen_overseer_privately(client, monkeypatch, attention):
    # A done-unseen overseer (finished a chunk while Bill was away) wakes him once, then
    # is acked so it can't re-wake in a loop — WITHOUT clearing the user's own dashboard
    # "unseen" overlay on that session, which is theirs, not Bill's.
    attention.mark_attention("port", "idle")
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": "idle",
                "unseen": True,
                "watched": True,
            }
        ],
    )
    first = client.get("/api/bill/fleet/wait", params={"timeout": 1}).json()
    assert first["woke"] is True
    assert attention.is_unseen("port"), "the user's own overlay must survive Bill seeing it"
    assert "port" in bill._overseer_acked
    second = client.get("/api/bill/fleet/wait", params={"timeout": 0.1}).json()
    assert second["woke"] is False  # acked -> no re-wake loop


def test_fleet_wait_still_wakes_on_a_blocked_overseer(client, monkeypatch):
    # A stuck overseer wakes on its state every time, never silenced by an ack.
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": "blocked",
                "unseen": True,
                "watched": True,
            }
        ],
    )
    assert client.get("/api/bill/fleet/wait", params={"timeout": 1}).json()["woke"] is True
    assert client.get("/api/bill/fleet/wait", params={"timeout": 1}).json()["woke"] is True


def test_fleet_wait_never_wakes_on_worker_state(client, monkeypatch):
    # Workers are their overseer's concern, never Bill's: a blocked or dead worker must
    # not wake his supervise loop, no matter how unseen.
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "worker",
                "task": "port-697",
                "session": "port-697",
                "parent": "port",
                "state": "blocked",
                "unseen": True,
            },
            {
                "role": "worker",
                "task": "port-698",
                "parent": "port",
                "state": "dead",
                "unseen": True,
            },
        ],
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 0.1, "as_session": "bill"}).json()
    assert body["woke"] is False


def test_fleet_wait_wakes_an_overseer_on_its_own_worker(client, monkeypatch):
    # An overseer supervising its own crew: a blocked worker under `port` wakes `port`.
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": "idle",
                "unseen": False,
                "watched": True,
            },
            {
                "role": "worker",
                "task": "port-697",
                "session": "port-697",
                "parent": "port",
                "state": "blocked",
                "unseen": False,
            },
        ],
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 1, "as_session": "port"}).json()
    assert body["woke"] is True


def test_fleet_wait_scopes_an_overseer_to_its_own_workers(client, monkeypatch):
    # `port` must not be woken by `aio`'s worker — each overseer watches only its own crew.
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "worker",
                "task": "aio-12",
                "session": "aio-12",
                "parent": "aio",
                "state": "blocked",
                "unseen": True,
            },
        ],
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 0.1, "as_session": "port"}).json()
    assert body["woke"] is False


def test_fleet_wait_wakes_bill_on_an_orphan_worker(client, monkeypatch):
    # A worker for a repo with no live overseer has no parent — nobody else can watch it,
    # so it is Bill's own direct report and must wake him.
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "worker",
                "task": "solo-1",
                "session": "solo-1",
                "parent": None,
                "state": "blocked",
                "unseen": True,
            },
        ],
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 1, "as_session": "bill"}).json()
    assert body["woke"] is True


@pytest.fixture
def watch_registry(tmp_path, monkeypatch):
    """Real watch + babysit registries, redirected off the user's real config."""
    from lumbergh import babysit, bill_watch

    monkeypatch.setattr(bill_watch, "WATCH_PATH", tmp_path / "bill_watch.json")
    monkeypatch.setattr(babysit, "BABYSITS_PATH", tmp_path / "babysits.json")
    return bill_watch


def _unwatched_overseer(**over):
    return {
        "role": "overseer",
        "task": "scratch-738b3c4e",
        "session": "scratch-738b3c4e",
        "state": "idle",
        "unseen": True,
        "watched": False,
        **over,
    }


def test_fleet_wait_ignores_a_session_nobody_handed_bill(client, monkeypatch):
    """The bug: every live session shows up as an `overseer` row, so a session the *user*
    opened for themselves — idle and unseen the moment they walked away from it — read to
    Bill as a report that had delivered work, and he dove into its transcript."""
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [_unwatched_overseer()],  # noqa: ARG005
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 0.1}).json()
    assert body["woke"] is False


def test_fleet_wait_ignores_even_a_blocked_session_that_is_not_bills(client, monkeypatch):
    # The user's own session waiting on the user is not Bill's to answer.
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            _unwatched_overseer(state="blocked")
        ],
    )
    assert client.get("/api/bill/fleet/wait", params={"timeout": 0.1}).json()["woke"] is False


def test_fleet_still_lists_a_session_that_is_not_bills_but_never_flags_it(client, monkeypatch):
    # He needs to see it to know the repo already has an overseer to delegate to; he just
    # must not be told it wants him.
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            _unwatched_overseer(),
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": "idle",
                "unseen": True,
                "watched": True,
            },
        ],
    )
    body = client.get("/api/bill/fleet").json()
    by_task = {r["task"]: r for r in body["tasks"]}
    assert by_task["scratch-738b3c4e"]["attention"] is False
    assert by_task["port"]["attention"] is True


def test_fleet_rows_mark_the_overseers_bill_watches(monkeypatch, watch_registry):
    from lumbergh import babysit

    babysit.start("port", "/repo/port", "2026-08-02T20:00:00+00:00")
    watch_registry.engage("aio", "2026-08-02T20:00:00+00:00")
    monkeypatch.setattr(
        bill.fleet,
        "snapshot",
        lambda *a, **k: [  # noqa: ARG005
            {"role": "overseer", "task": "port", "state": "idle"},
            {"role": "overseer", "task": "aio", "state": "idle"},
            {"role": "overseer", "task": "scratch-1", "state": "idle"},
            {"role": "worker", "task": "port-7", "state": "working"},
        ],
    )
    monkeypatch.setattr("lumbergh.routers.worktrees._live_sessions", dict)
    rows = {r["task"]: r for r in bill._fleet_rows(None)}
    assert rows["port"]["watched"] is True, "a babysit is a standing watch"
    assert rows["aio"]["watched"] is True, "a delegation is a one-shot watch"
    assert rows["scratch-1"]["watched"] is False
    assert "watched" not in rows["port-7"], "workers are scoped by their parent, not by watch"


@pytest.mark.usefixtures("attention")
def test_being_shown_the_delivered_chunk_ends_the_delegation(client, monkeypatch, watch_registry):
    # Bill delegated to `port`; `port` did the work and went idle+unseen. That wake is the
    # answer he was waiting for, so the engagement is spent — `port` goes back to being the
    # user's own session until Bill is given it again.
    watch_registry.engage("port", "2026-08-02T20:00:00+00:00")
    bill._overseer_acked.clear()
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": "idle",
                "unseen": True,
                "watched": True,
            }
        ],
    )
    assert client.get("/api/bill/fleet/wait", params={"timeout": 1}).json()["woke"] is True
    assert watch_registry.watched() == set(), "the one-shot delegation is spent"


@pytest.mark.usefixtures("attention")
def test_a_babysit_outlives_the_chunk_it_delivers(client, monkeypatch, watch_registry):
    # A babysit is standing: it keeps waking Bill until the user cancels it.
    from lumbergh import babysit

    babysit.start("port", "/repo/port", "2026-08-02T20:00:00+00:00")
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": "idle",
                "unseen": True,
                "watched": True,
            }
        ],
    )
    client.get("/api/bill/fleet/wait", params={"timeout": 1})
    assert watch_registry.watched() == {"port"}


def test_delegating_to_an_already_idle_session_does_not_read_as_an_instant_answer(
    client, monkeypatch, attention, watch_registry
):
    # Delegation almost always lands on a session that is *already* idle+unseen from
    # whatever it did last. That stale episode must not wake Bill and burn the engagement
    # before the overseer has even started on what he asked for.
    attention.mark_attention("port", "idle")
    bill._overseer_acked.clear()
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": "idle",
                "unseen": True,
                "watched": True,
            }
        ],
    )
    bill.engage_overseer("port")
    assert client.get("/api/bill/fleet/wait", params={"timeout": 0.1}).json()["woke"] is False
    assert watch_registry.watched() == {"port"}, "still owed an answer"


@pytest.mark.usefixtures("attention", "watch_registry")
def test_a_delegated_overseer_wakes_bill_once_it_has_actually_worked(client, monkeypatch):
    # ...and the moment it goes to work, the pre-ack is dropped, so the chunk it then
    # delivers wakes him normally.
    bill._overseer_acked.clear()
    states = iter(["working", "idle", "idle"])
    monkeypatch.setattr(bill, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "role": "overseer",
                "task": "port",
                "session": "port",
                "state": next(states, "idle"),
                "unseen": True,
                "watched": True,
            }
        ],
    )
    bill.engage_overseer("port")
    assert client.get("/api/bill/fleet/wait", params={"timeout": 2}).json()["woke"] is True


def test_fleet_rows_carry_target_and_run(monkeypatch):
    """A window-level batch worker is recorded with a `session:window` target distinct
    from the bare tmux session (Task 5's registry). The fleet row must surface that
    target (plus its run group) and resolve state against it, not the bare session —
    otherwise every window of a batch collapses onto one shared status."""
    from lumbergh import worktrees
    from lumbergh.idle_detector import SessionState

    monkeypatch.setattr("lumbergh.routers.worktrees._live_sessions", dict)
    monkeypatch.setattr(
        worktrees,
        "reconcile_all",
        lambda live: [  # noqa: ARG005
            {"path": "/wt/644", "repo": "port", "branch": "kb-644", "session": "port"}
        ],
    )
    monkeypatch.setattr(
        worktrees,
        "get_entry",
        lambda p: {  # noqa: ARG005
            "parent_repo": "/repo/port",
            "target": "port:fleet-644",
            "run": "batch-9",
            "kind": "ship",
            "origin": "bill",
        },
    )
    state_queries = []
    monkeypatch.setattr(
        bill.idle_monitor,
        "get_state",
        lambda t: state_queries.append(t) or SessionState.WORKING,
    )

    rows = bill._fleet_rows("bill")

    assert rows[0]["target"] == "port:fleet-644"
    assert rows[0]["run"] == "batch-9"
    assert rows[0]["task"] == "port:fleet-644"
    assert state_queries == ["port:fleet-644"], (
        "state must be resolved against the window target, not the bare tmux session"
    )


def test_outcome_of_reads_the_workers_final_line(monkeypatch):
    class _Event:
        def __init__(self, text):
            self.text = text
            self.tool_summary = ""

    class _Adapter:
        def read_new(self):
            return [_Event("ran the tests"), _Event("DELIVERED: https://example.test/pull/7")]

    monkeypatch.setattr(bill, "resolve_adapter", lambda *a, **kw: _Adapter())  # noqa: ARG005
    monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/w"})
    assert bill._outcome_of("w-a") == "DELIVERED: https://example.test/pull/7"


def test_outcome_of_is_none_without_a_transcript(monkeypatch):
    monkeypatch.setattr(bill, "resolve_adapter", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_session_meta", lambda name: {})  # noqa: ARG005
    assert bill._outcome_of("w-a") is None


def test_outcome_of_is_none_when_the_transcript_is_corrupt(monkeypatch):
    def _blow_up(*a, **kw):  # noqa: ARG001
        raise ValueError("corrupt transcript")

    monkeypatch.setattr(bill, "resolve_adapter", _blow_up)
    monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/w"})
    assert bill._outcome_of("w-a") is None


def test_derive_name_sanitizes_and_uniquifies():
    assert bill._derive_name("feat/flaky-login", set()) == "feat-flaky-login"
    assert bill._derive_name("feat/flaky-login", {"feat-flaky-login"}) == "feat-flaky-login-2"
    assert (
        bill._derive_name("feat/flaky-login", {"feat-flaky-login", "feat-flaky-login-2"})
        == "feat-flaky-login-3"
    )


def test_spawn_rejects_a_missing_brief(client, tmp_path):
    missing = tmp_path / "nope.md"
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(missing),
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "brief"
    assert str(missing) in detail["error"], (
        "the error must name the exact path searched — an absolute --brief is "
        "never resolved against Bill's home, the CLI already absolutized it "
        "against the caller's cwd before this request arrived"
    )
    assert "resolved against" not in detail["help"], (
        "the help must not assert a resolution rule that didn't apply to this request"
    )


def test_spawn_rejects_a_missing_relative_brief(client, tmp_path):
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": "briefs/nope.md",
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "brief"
    assert str(bill.bill_bundle.home() / "briefs" / "nope.md") in detail["error"]
    assert "resolved against" in detail["help"]


def test_spawn_rejects_an_unknown_kind(client, tmp_path):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "wander",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "kind"


def test_spawn_rejects_a_repo_without_git(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    create_calls = []
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: create_calls.append((a, kw)),
    )

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "repo"
    assert create_calls == []


def test_spawn_surfaces_a_worktree_failure(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"error": "branch already checked out"},  # noqa: ARG005
    )
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["stage"] == "worktree"
    assert "already checked out" in body["error"]


def test_spawn_unwinds_the_worktree_when_the_session_fails(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    reaped = {}

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )

    def boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("tmux is not installed")

    monkeypatch.setattr(bill, "create_tmux_session", boom)

    def record_reap(path, **kw):  # noqa: ARG001
        reaped["path"] = str(path)
        return {"status": "removed"}

    monkeypatch.setattr(bill.worktrees, "reap", record_reap)
    removed = []
    monkeypatch.setattr(bill.worktrees, "remove_entry", removed.append)

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "session"
    assert reaped["path"] == str(tmp_path / "wt")
    assert removed == [Path(tmp_path / "wt")]


def test_spawn_rejects_a_name_that_is_already_live(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", lambda: {"feat-x": {}})
    create_calls = []
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: create_calls.append((a, kw)),
    )

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
            "name": "feat-x",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "name"
    assert create_calls == []


def test_spawn_rejects_a_name_with_a_slash(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    create_calls = []
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: create_calls.append((a, kw)),
    )

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
            "name": "feat/x",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "name"
    assert create_calls == []


def test_spawn_accepts_a_valid_name(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_deliver_brief", lambda *a, **kw: bill.DeliveryResult(True, ""))  # noqa: ARG005

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
            "name": "task-slug",
        },
    )
    assert r.status_code == 200
    assert r.json()["session"] == "task-slug"


def test_spawn_seeds_worker_skills_before_launch(client, tmp_path, monkeypatch):
    # A spawned worker must have the ship/scout contract available, so the brief needn't
    # restate it. Spawn seeds the skills before the agent boots.
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )
    calls = []
    from lumbergh.agent_cli import skill

    monkeypatch.setattr(skill, "ensure_worker_skills", lambda: calls.append(True) or [])
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_deliver_brief", lambda *a, **kw: bill.DeliveryResult(True, ""))  # noqa: ARG005

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
            "name": "task-slug",
        },
    )
    assert r.status_code == 200
    assert calls == [True]


def test_spawn_preserves_the_original_stage_when_unwind_itself_fails(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )

    def session_boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("tmux is not installed")

    def reap_boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("git worktree remove exploded")

    monkeypatch.setattr(bill, "create_tmux_session", session_boom)
    monkeypatch.setattr(bill.worktrees, "reap", reap_boom)

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["stage"] == "session"
    assert "tmux is not installed" in body["error"]
    assert "manual cleanup" in body["help"]


def test_spawn_unwinds_fully_when_the_brief_never_delivers(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    killed = []
    reaped = {}
    removed = []

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(
        bill,
        "_deliver_brief",
        lambda *a, **kw: bill.DeliveryResult(False, "worker never reached a ready input prompt"),  # noqa: ARG005
    )
    monkeypatch.setattr(bill, "kill_tmux_session", killed.append)

    def record_reap(path, **kw):  # noqa: ARG001
        reaped["path"] = str(path)
        return {"status": "removed"}

    monkeypatch.setattr(bill.worktrees, "reap", record_reap)
    monkeypatch.setattr(bill.worktrees, "remove_entry", removed.append)

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["stage"] == "delivery"
    # The failure carries the delivery reason and points Bill at the pane, not a
    # bare "check tmux" — the terminal is exactly what he needs to look at.
    assert "ready input prompt" in body["error"]
    assert "lb read --source pane" in body["help"]
    assert killed == ["feat-x"]
    assert reaped["path"] == str(tmp_path / "wt")
    assert removed == [Path(tmp_path / "wt")]


def test_spawn_unwinds_fully_when_storing_the_session_raises(client, tmp_path, monkeypatch):
    """Recording the task has its own stage: "check tmux" is the wrong advice for a
    caller whose session store is broken."""
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    killed = []
    reaped = {}
    removed = []

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005

    def boom(**kw):  # noqa: ARG001
        raise RuntimeError("disk full")

    monkeypatch.setattr(bill, "_store_session", boom)
    monkeypatch.setattr(bill, "kill_tmux_session", killed.append)

    def record_reap(path, **kw):  # noqa: ARG001
        reaped["path"] = str(path)
        return {"status": "removed"}

    monkeypatch.setattr(bill.worktrees, "reap", record_reap)
    monkeypatch.setattr(bill.worktrees, "remove_entry", removed.append)

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["stage"] == "record"
    assert "disk full" in body["error"]
    assert killed == ["feat-x"]
    assert reaped["path"] == str(tmp_path / "wt")
    assert removed == [Path(tmp_path / "wt")]


def test_spawn_happy_path_records_the_task_and_delivers_the_brief(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    sent = {}
    stored = {}

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: stored.update(kw))
    monkeypatch.setattr(
        bill,
        "deliver_when_ready",
        lambda name, text: sent.update(name=name, text=text) or bill.DeliveryResult(True, ""),
    )

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "scout",
            "brief_path": str(brief),
            "task_intent": "figure out the flaky login test",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session"] == "feat-x"
    assert body["kind"] == "scout"
    assert stored["name"] == "feat-x"
    assert str(brief) in sent["text"]


def test_fleet_isolates_a_row_whose_transcript_read_raises(client, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.worktrees._live_sessions", dict)
    monkeypatch.setattr(
        bill.fleet,
        "snapshot",
        lambda *a, **kw: [  # noqa: ARG005
            {"session": "broken", "task": "w-broken"},
            {"session": "healthy", "task": "w-healthy"},
        ],
    )
    monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/w"})

    class _Event:
        def __init__(self, text):
            self.text = text

    class _RaisingAdapter:
        def read_new(self):
            raise ValueError("corrupt transcript")

    class _HealthyAdapter:
        def read_new(self):
            return [_Event("DELIVERED: https://example.test/pull/1")]

    def resolve(session_name, cwd, provider):  # noqa: ARG001
        return _RaisingAdapter() if session_name == "broken" else _HealthyAdapter()

    monkeypatch.setattr(bill, "resolve_adapter", resolve)

    body = client.get("/api/bill/fleet").json()
    rows_by_session = {row["session"]: row for row in body["tasks"]}
    assert rows_by_session["broken"]["outcome"] is None
    assert rows_by_session["healthy"]["outcome"] == "DELIVERED: https://example.test/pull/1"


def test_summon_creates_bill_and_materializes_his_home(client, tmp_path, monkeypatch):
    spawned = {}
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        bill,
        "create_tmux_session",
        lambda name, workdir, **kw: spawned.update(  # noqa: ARG005
            name=name, workdir=str(workdir)
        ),
    )
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005

    body = client.post("/api/bill/summon").json()
    assert body == {
        "session": "bill",
        "workdir": str(tmp_path / "bill"),
        "existing": False,
    }
    assert (tmp_path / "bill" / "AGENTS.md").is_file()
    assert spawned["name"] == "bill"


def test_summon_returns_the_existing_session_without_respawning(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", lambda: {"bill": {}})
    monkeypatch.setattr(
        "lumbergh.routers.sessions.get_stored_sessions",
        lambda: {"bill": {"workdir": str(tmp_path / "bill")}},
    )
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")

    def boom(*a, **kw):  # noqa: ARG001
        raise AssertionError("must not spawn a second Bill")

    monkeypatch.setattr(bill, "create_tmux_session", boom)
    body = client.post("/api/bill/summon").json()
    assert body["existing"] is True
    assert body["session"] == "bill"


def test_summon_refuses_when_bill_is_held_by_a_different_workdir(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", lambda: {"bill": {}})
    monkeypatch.setattr(
        "lumbergh.routers.sessions.get_stored_sessions",
        lambda: {"bill": {"workdir": str(tmp_path / "someones-worktree")}},
    )
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")

    def boom(*a, **kw):  # noqa: ARG001
        raise AssertionError("must not touch a session that isn't Bill")

    monkeypatch.setattr(bill, "create_tmux_session", boom)

    r = client.post("/api/bill/summon")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "identity"
    assert str(tmp_path / "someones-worktree") in detail["error"]
    assert detail["workdir"] == str(tmp_path / "bill")


def test_summon_refuses_an_unrecorded_live_bill(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", lambda: {"bill": {}})
    monkeypatch.setattr("lumbergh.routers.sessions.get_stored_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")

    def boom(*a, **kw):  # noqa: ARG001
        raise AssertionError("must not touch an unverifiable session")

    monkeypatch.setattr(bill, "create_tmux_session", boom)

    r = client.post("/api/bill/summon")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "identity"
    assert detail["workdir"] == str(tmp_path / "bill")


def test_summon_renders_the_configured_personality(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_settings", lambda: {"bill": {"personality": "lumbergh"}})

    client.post("/api/bill/summon")
    assert (tmp_path / "bill" / "AGENTS.md").read_text() == bill.bill_bundle.render("lumbergh")


def test_summon_uses_the_configured_harness(client, tmp_path, monkeypatch):
    spawned = {}
    stored = {}
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        bill,
        "create_tmux_session",
        lambda name, workdir, launch_command=None, **kw: spawned.update(  # noqa: ARG005
            launch_command=launch_command
        ),
    )
    monkeypatch.setattr(bill, "_store_session", lambda **kw: stored.update(kw))
    monkeypatch.setattr(bill, "_settings", lambda: {"bill": {"harness": "claude-code"}})

    client.post("/api/bill/summon")
    assert "claude" in spawned["launch_command"]
    assert stored["agent_provider"] == "claude-code"


def test_summon_renders_a_custom_personality(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(
        bill,
        "_settings",
        lambda: {
            "bill": {"personality": "custom", "customPersonality": "You are Bill the pirate."}
        },
    )

    client.post("/api/bill/summon")
    assert "pirate" in (tmp_path / "bill" / "AGENTS.md").read_text()


def test_summon_kills_the_freshly_created_session_when_storing_fails(tmp_path, monkeypatch):
    tmux_has_bill = {"alive": False}
    killed = []

    def fake_create(*a, **kw):  # noqa: ARG001
        tmux_has_bill["alive"] = True

    def fake_kill(name):
        killed.append(name)
        tmux_has_bill["alive"] = False

    monkeypatch.setattr(
        "lumbergh.routers.sessions.get_live_sessions",
        lambda: {"bill": {}} if tmux_has_bill["alive"] else {},
    )
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(bill, "create_tmux_session", fake_create)
    monkeypatch.setattr(bill, "kill_tmux_session", fake_kill)

    def boom(**kw):  # noqa: ARG001
        raise RuntimeError("disk full")

    monkeypatch.setattr(bill, "_store_session", boom)

    app = FastAPI()
    app.include_router(bill.router)
    raw_client = TestClient(app, raise_server_exceptions=False)

    r = raw_client.post("/api/bill/summon")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "record"
    assert "disk full" in detail["error"]
    assert detail["workdir"] == str(tmp_path / "bill")
    assert killed == ["bill"]

    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    retry = raw_client.post("/api/bill/summon")
    assert retry.status_code == 200
    assert retry.json()["existing"] is False


def test_summon_recovers_when_a_racing_request_wins_the_create(client, tmp_path, monkeypatch):
    calls = {"n": 0}

    def live():
        calls["n"] += 1
        return {} if calls["n"] == 1 else {"bill": {}}

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", live)
    monkeypatch.setattr(
        "lumbergh.routers.sessions.get_stored_sessions",
        lambda: {"bill": {"workdir": str(tmp_path / "bill")}},
    )
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")

    def boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("duplicate session: bill")

    monkeypatch.setattr(bill, "create_tmux_session", boom)

    body = client.post("/api/bill/summon").json()
    assert body == {"session": "bill", "workdir": str(tmp_path / "bill"), "existing": True}


def test_summon_surfaces_a_genuine_tmux_failure(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")

    def boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("tmux is not installed")

    monkeypatch.setattr(bill, "create_tmux_session", boom)

    r = client.post("/api/bill/summon")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "session"
    assert "tmux is not installed" in detail["error"]
    assert detail["workdir"] == str(tmp_path / "bill")


def test_summon_refuses_when_the_harness_binary_is_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: None)  # noqa: ARG005

    def boom(*a, **kw):  # noqa: ARG001
        raise AssertionError("must not create a session for a missing harness")

    monkeypatch.setattr(bill, "create_tmux_session", boom)

    r = client.post("/api/bill/summon")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "harness"
    assert "pi" in detail["error"]
    assert "pi" in detail["help"]
    assert detail["workdir"] == str(tmp_path / "bill")


def test_summon_creates_normally_when_the_harness_binary_is_present(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005

    body = client.post("/api/bill/summon").json()
    assert body["existing"] is False


def test_write_brief_refuses_a_path_outside_bills_home(client, tmp_path, monkeypatch):
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    r = client.post("/api/bill/brief", json={"path": str(tmp_path / "escape.md"), "body": "x"})
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "path"
    assert not (tmp_path / "escape.md").exists()


def test_write_brief_accepts_a_path_inside_briefs(client, tmp_path, monkeypatch):
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    (tmp_path / "bill" / "briefs").mkdir(parents=True)
    r = client.post(
        "/api/bill/brief", json={"path": str(tmp_path / "bill" / "briefs" / "w.md"), "body": "hi"}
    )
    assert r.status_code == 200
    assert (tmp_path / "bill" / "briefs" / "w.md").read_text() == "hi"


def test_write_brief_creates_missing_parent_directories(client, tmp_path, monkeypatch):
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    nested = tmp_path / "bill" / "briefs" / "sub" / "w.md"
    r = client.post("/api/bill/brief", json={"path": str(nested), "body": "hi"})
    assert r.status_code == 200
    assert nested.read_text() == "hi"


def test_spawn_accepts_a_brief_path_relative_to_bills_home(client, tmp_path, monkeypatch):
    """The invocation AGENTS.md documents: Bill writes ``briefs/<slug>.md`` from his home,
    then spawns with ``--brief briefs/<slug>.md``. Resolving that against the *server's*
    cwd made the documented command fail with "write the brief before spawning" — telling
    a weak model to redo the thing it had just done."""
    home = tmp_path / "bill"
    (home / "briefs").mkdir(parents=True)
    (home / "briefs" / "flaky-login.md").write_text("# Task: fix the flaky login test\n")
    repo = tmp_path / "app"
    (repo / ".git").mkdir(parents=True)
    sent = {}

    monkeypatch.setattr(bill.bill_bundle, "home", lambda: home)
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(
        bill,
        "deliver_when_ready",
        lambda _name, text: sent.update(text=text) or bill.DeliveryResult(True, ""),
    )

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(repo),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": "briefs/flaky-login.md",
            "name": "flaky-login",
        },
    )

    assert r.status_code == 200, r.text
    assert r.json()["brief_path"] == str(home / "briefs" / "flaky-login.md")
    assert str(home / "briefs" / "flaky-login.md") in sent["text"]


def test_spawn_help_for_a_missing_brief_names_the_path_it_looked_in(client, tmp_path, monkeypatch):
    """ "Write the brief" is unhelpful when the brief exists and the path was wrong, so the
    help has to say where the server actually looked."""
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": "briefs/nope.md",
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "brief"
    assert str(tmp_path / "bill" / "briefs" / "nope.md") in detail["error"]
    assert str(tmp_path / "bill") in detail["help"]


def test_scout_report_path_lives_in_bills_home_not_beside_the_brief(tmp_path, monkeypatch):
    """A brief in a subdirectory of ``briefs/`` used to send the scout's report two levels
    up from wherever the brief happened to sit; the real invariant is Bill's home."""
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    nested = tmp_path / "bill" / "briefs" / "sub" / "w.md"

    text = bill._brief_delivery(nested, "scout", "w")

    assert str(tmp_path / "bill" / "reports" / "w.md") in text


def test_spawn_keeps_the_registry_row_when_the_worktree_cannot_be_removed(
    client, tmp_path, monkeypatch
):
    """``worktrees.reap`` returns its failures instead of raising. Dropping the registry
    row anyway would leave the directory on disk with nothing pointing at it — invisible
    to ``lb fleet`` and to reconcile — while the caller was told cleanup succeeded."""
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    (tmp_path / ".git").mkdir()
    removed = []

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )

    def session_boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("tmux is not installed")

    monkeypatch.setattr(bill, "create_tmux_session", session_boom)
    monkeypatch.setattr(
        bill.worktrees,
        "reap",
        lambda *a, **kw: {"error": "worktree is locked", "reason": "locked"},  # noqa: ARG005
    )
    monkeypatch.setattr(bill.worktrees, "remove_entry", removed.append)

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )

    body = r.json()["detail"]
    assert body["stage"] == "session"
    assert "tmux is not installed" in body["error"]
    assert "manual cleanup" in body["help"]
    assert removed == [], "the registry row outlived a worktree that is still on disk"


@pytest.mark.parametrize(
    "launch_command",
    [
        "ANTHROPIC_API_KEY=$KEY claude",
        "(pi)",
        ">/tmp/pi.log pi",
        "{pi,}",
    ],
)
def test_harness_check_is_skipped_when_the_first_token_is_not_a_program(launch_command):
    """``shutil.which`` would fail on each of these first tokens and summon would refuse a
    setup that actually works. A false refusal is worse than the silent pane failure this
    check exists to catch, so an unrecognizable shape skips the check."""
    assert bill._harness_binary(launch_command) is None


@pytest.mark.parametrize(
    ("launch_command", "expected"),
    [
        ("pi", "pi"),
        ("claude --continue || claude", "claude"),
        ("/usr/local/bin/pi --resume", "/usr/local/bin/pi"),
    ],
)
def test_harness_check_still_names_the_program_for_real_launch_commands(launch_command, expected):
    assert bill._harness_binary(launch_command) == expected


def test_spawn_into_creates_window_worker(monkeypatch, tmp_path):
    from lumbergh.routers import bill

    (tmp_path / "repo" / ".git").mkdir(parents=True)
    brief = tmp_path / "brief.md"
    brief.write_text("do the thing")

    monkeypatch.setattr(bill, "_resolve_brief", lambda p: brief)  # noqa: ARG005
    monkeypatch.setattr(
        "lumbergh.routers.bill.get_live_sessions"
        if hasattr(bill, "get_live_sessions")
        else "lumbergh.routers.sessions.get_live_sessions",
        dict,
        raising=False,
    )
    monkeypatch.setattr(
        "lumbergh.routers.bill.list_session_windows",
        lambda s: [],  # noqa: ARG005
        raising=False,
    )
    monkeypatch.setattr(
        "lumbergh.routers.bill.worktrees.create",
        lambda *a, **k: (  # noqa: ARG005
            {"path": str(tmp_path / "wt")} | ({"target": k.get("target"), "run": k.get("run")})
        ),
    )
    captured = {}

    def fake_window(session, window, workdir, launch_command="x"):  # noqa: ARG001
        captured["target"] = f"{session}:{window}"
        return f"{session}:{window}"

    monkeypatch.setattr("lumbergh.routers.bill.create_tmux_window", fake_window, raising=False)
    monkeypatch.setattr(
        "lumbergh.routers.bill._deliver_brief",
        lambda *a, **k: bill.DeliveryResult(True, ""),  # noqa: ARG005
    )
    stored = {}
    monkeypatch.setattr("lumbergh.routers.bill._store_session", lambda **k: stored.update(k))

    body = bill.SpawnBody(
        repo=str(tmp_path / "repo"),
        branch="kb-644",
        kind="ship",
        brief_path=str(brief),
        name="fleet-644",
        into="port",
        run="batch-9",
    )
    resp = bill.spawn(body)
    assert resp["session"] == "port:fleet-644"
    assert captured["target"] == "port:fleet-644"
    assert stored == {}  # window workers are NOT written to the session store


class TestBabysitEndpoints:
    @pytest.fixture(autouse=True)
    def _isolated_registry(self, tmp_path, monkeypatch):
        from lumbergh import babysit

        monkeypatch.setattr(babysit, "BABYSITS_PATH", tmp_path / "babysits.json")

    def test_start_resolves_repo_from_session_workdir(self, client, monkeypatch):
        monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/repo/port"})
        resp = client.post("/api/bill/babysit", json={"session": "port"})
        assert resp.status_code == 200
        assert resp.json()["repo"] == "/repo/port"

    def test_explicit_repo_wins(self, client, monkeypatch):
        monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/wrong"})
        resp = client.post("/api/bill/babysit", json={"session": "port", "repo": "/right"})
        assert resp.json()["repo"] == "/right"

    def test_list_then_stop_roundtrip(self, client, monkeypatch):
        monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/repo/port"})
        client.post("/api/bill/babysit", json={"session": "port"})
        client.post("/api/bill/babysit", json={"session": "aio", "repo": "/repo/aio"})

        listed = client.get("/api/bill/babysit").json()["babysits"]
        assert {row["session"] for row in listed} == {"port", "aio"}

        stopped = client.request("DELETE", "/api/bill/babysit", params={"session": "port"})
        assert stopped.json() == {"session": "port", "stopped": True}
        assert {r["session"] for r in client.get("/api/bill/babysit").json()["babysits"]} == {"aio"}

    def test_refresh_runs_the_ritual_for_a_babysat_session(self, client, monkeypatch):
        monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/repo/port"})
        client.post("/api/bill/babysit", json={"session": "port"})

        called = {}

        async def _fake_refresh(session):
            called["session"] = session
            return ("refreshed", [])

        monkeypatch.setattr("lumbergh.babysit.refresh", _fake_refresh)
        resp = client.post("/api/bill/babysit/refresh", json={"session": "port"})

        assert resp.status_code == 200
        assert resp.json() == {"session": "port", "refreshed": True}
        assert called["session"] == "port"

    def test_refresh_is_refused_while_the_session_supervises_live_workers(
        self, client, monkeypatch
    ):
        """The incident: `/clear` landed on an overseer with five running workers, wiping
        the context supervising them. Bill asked for it, so the veto lives in the server."""
        monkeypatch.setattr(bill, "_session_meta", lambda _name: {"workdir": "/repo/port"})
        client.post("/api/bill/babysit", json={"session": "port"})

        async def _fake_refresh(_session):
            return ("held", ["issue-792", "issue-804"])

        monkeypatch.setattr("lumbergh.babysit.refresh", _fake_refresh)
        resp = client.post("/api/bill/babysit/refresh", json={"session": "port"})

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "issue-792" in detail["error"]
        assert "waiting on its crew" in detail["help"]

    def test_refresh_rejects_a_session_that_is_not_babysat(self, client):
        resp = client.post("/api/bill/babysit/refresh", json={"session": "nope"})
        assert resp.status_code == 400
        assert "not being babysat" in resp.json()["detail"]["error"]
