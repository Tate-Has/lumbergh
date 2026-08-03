import asyncio
from importlib import reload

import pytest

from lumbergh import constants

# The refresh ritual must land in the session's *agent* window. A bare `port` would type
# `/clear` into whichever window the user has selected — see targets.py.
PORT_REF = "port:{start}"


@pytest.fixture
def babysit(tmp_path, monkeypatch):
    """A babysit module whose registry lives under a throwaway CONFIG_DIR."""
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path))
    reload(constants)
    from lumbergh import babysit as mod

    reload(mod)
    return mod


def _repo_with_config(tmp_path, body: str):
    (tmp_path / ".lumbergh.toml").write_text(body)
    return tmp_path


class TestRegistry:
    def test_start_then_listed_and_babysat(self, babysit):
        babysit.start("port", "/repo/port", "2026-08-01T00:00:00Z")
        assert babysit.is_babysat("port")
        assert babysit.babysat_sessions() == {"port"}
        assert babysit.list_all() == [
            {"session": "port", "repo": "/repo/port", "added_at": "2026-08-01T00:00:00Z"}
        ]

    def test_stop_removes(self, babysit):
        babysit.start("port", "/repo/port", "t")
        assert babysit.stop("port") is True
        assert not babysit.is_babysat("port")

    def test_stop_unknown_is_false(self, babysit):
        assert babysit.stop("nope") is False

    def test_multiple_concurrent_are_independent(self, babysit):
        babysit.start("port", "/repo/port", "t")
        babysit.start("aio", "/repo/aio", "t")
        babysit.stop("port")
        assert babysit.babysat_sessions() == {"aio"}

    def test_survives_reload(self, babysit):
        babysit.start("port", "/repo/port", "t")
        reload(babysit)
        assert babysit.is_babysat("port")

    def test_corrupt_registry_reads_empty(self, babysit):
        babysit.BABYSITS_PATH.write_text("{not json")
        assert babysit.babysat_sessions() == set()

    def test_repo_of(self, babysit):
        babysit.start("port", "/repo/port", "t")
        assert babysit.repo_of("port").name == "port"
        assert babysit.repo_of("unknown") is None


class TestConfig:
    def test_defaults_when_no_repo(self, babysit):
        cfg = babysit.read_config(None)
        assert cfg["refresh_ready"] == "⟳ REFRESH-READY"
        assert cfg["on_refresh"] == ["/clear", "/fleet-start"]

    def test_defaults_when_no_dotfile(self, babysit, tmp_path):
        assert babysit.read_config(tmp_path)["backlog_empty"] == "⟳ BACKLOG-EMPTY"

    def test_overrides(self, babysit, tmp_path):
        repo = _repo_with_config(
            tmp_path,
            '[babysit]\nrefresh_ready = "CYCLE-ME"\non_refresh = ["/clear", "/go"]\n',
        )
        cfg = babysit.read_config(repo)
        assert cfg["refresh_ready"] == "CYCLE-ME"
        assert cfg["on_refresh"] == ["/clear", "/go"]
        assert cfg["backlog_empty"] == "⟳ BACKLOG-EMPTY"  # untouched key keeps default


class TestDecide:
    def test_refresh_sentinel(self, babysit):
        cfg = babysit.read_config(None)
        assert babysit.decide("done.\n⟳ REFRESH-READY", cfg) == babysit.REFRESH

    def test_empty_sentinel(self, babysit):
        cfg = babysit.read_config(None)
        assert babysit.decide("nothing left ⟳ BACKLOG-EMPTY", cfg) == babysit.EMPTY

    def test_empty_wins_over_refresh(self, babysit):
        cfg = babysit.read_config(None)
        text = "⟳ REFRESH-READY ... ⟳ BACKLOG-EMPTY"
        assert babysit.decide(text, cfg) == babysit.EMPTY

    def test_plain_idle_is_none(self, babysit):
        cfg = babysit.read_config(None)
        assert babysit.decide("just finished a chunk", cfg) == babysit.NONE

    def test_empty_text_is_none(self, babysit):
        assert babysit.decide("", babysit.read_config(None)) == babysit.NONE


class TestOnIdle:
    def _wire(self, babysit, monkeypatch, text: str, in_flight: list[str] | None = None):
        sent: list[tuple[str, str]] = []
        cleared: list[str] = []
        monkeypatch.setattr(babysit, "last_agent_text", lambda _session: text)
        monkeypatch.setattr(babysit, "workers_in_flight", lambda _session: in_flight or [])
        monkeypatch.setattr(babysit, "REFRESH_GAP_SECONDS", 0)
        monkeypatch.setattr("lumbergh.tmux_pty.send_text", lambda s, t: sent.append((s, t)))
        monkeypatch.setattr("lumbergh.session_attention.clear_unseen", lambda s: cleared.append(s))

        async def _noop_persist():
            return None

        monkeypatch.setattr("lumbergh.session_attention.persist", _noop_persist)
        return sent, cleared

    def test_refresh_sends_commands_and_clears(self, babysit, monkeypatch):
        babysit.start("port", None, "t")
        sent, cleared = self._wire(babysit, monkeypatch, "⟳ REFRESH-READY")
        action = asyncio.run(babysit.on_idle("port"))
        assert action == babysit.REFRESH
        assert sent == [(PORT_REF, "/clear"), (PORT_REF, "/fleet-start")]
        assert cleared == ["port"]

    def test_empty_stops_the_babysit(self, babysit, monkeypatch):
        babysit.start("port", None, "t")
        sent, _ = self._wire(babysit, monkeypatch, "⟳ BACKLOG-EMPTY")
        action = asyncio.run(babysit.on_idle("port"))
        assert action == babysit.EMPTY
        assert sent == []
        assert not babysit.is_babysat("port")

    def test_plain_idle_does_nothing(self, babysit, monkeypatch):
        babysit.start("port", None, "t")
        sent, cleared = self._wire(babysit, monkeypatch, "still thinking")
        action = asyncio.run(babysit.on_idle("port"))
        assert action == babysit.NONE
        assert sent == []
        assert cleared == []
        assert babysit.is_babysat("port")

    def test_unbabysat_session_is_noop(self, babysit, monkeypatch):
        sent, _ = self._wire(babysit, monkeypatch, "⟳ REFRESH-READY")
        action = asyncio.run(babysit.on_idle("not-babysat"))
        assert action == babysit.NONE
        assert sent == []


class TestRefresh:
    """`babysit.refresh` is the manual refresh Bill triggers with `lb babysit --refresh` —
    the same /clear + restart the sentinel path sends, so it stays the one place that owns
    the load-bearing gap between the two commands."""

    def _wire(self, babysit, monkeypatch, in_flight: list[str] | None = None):
        sent: list[tuple[str, str]] = []
        cleared: list[str] = []
        monkeypatch.setattr(babysit, "workers_in_flight", lambda _session: in_flight or [])
        monkeypatch.setattr(babysit, "REFRESH_GAP_SECONDS", 0)
        monkeypatch.setattr("lumbergh.tmux_pty.send_text", lambda s, t: sent.append((s, t)))
        monkeypatch.setattr("lumbergh.session_attention.clear_unseen", lambda s: cleared.append(s))

        async def _noop_persist():
            return None

        monkeypatch.setattr("lumbergh.session_attention.persist", _noop_persist)
        return sent, cleared

    def test_sends_the_refresh_ritual(self, babysit, monkeypatch):
        babysit.start("port", None, "t")
        sent, cleared = self._wire(babysit, monkeypatch)
        assert asyncio.run(babysit.refresh("port")) == (babysit.REFRESHED, [])
        assert sent == [(PORT_REF, "/clear"), (PORT_REF, "/fleet-start")]
        assert cleared == ["port"]

    def test_unbabysat_session_refuses(self, babysit, monkeypatch):
        sent, _ = self._wire(babysit, monkeypatch)
        assert asyncio.run(babysit.refresh("not-babysat")) == (babysit.NOT_BABYSAT, [])
        assert sent == []


class TestRefreshHoldsWhileWorkersRun:
    """The incident: an overseer that has just dispatched a batch sits *idle* while its
    workers run — that is it waiting, not stalling. Bill (a small model, prompted to
    "advance" it) refreshed it anyway, and the `/clear` wiped the context supervising five
    in-flight workers. The session's own handoff contract says the same thing: hand off
    only with the fleet idle. So the server refuses, whoever asks."""

    def _wire(self, babysit, monkeypatch, in_flight):
        sent: list[tuple[str, str]] = []
        monkeypatch.setattr(babysit, "workers_in_flight", lambda _session: in_flight)
        monkeypatch.setattr(babysit, "REFRESH_GAP_SECONDS", 0)
        monkeypatch.setattr("lumbergh.tmux_pty.send_text", lambda s, t: sent.append((s, t)))
        monkeypatch.setattr("lumbergh.session_attention.clear_unseen", lambda _s: None)

        async def _noop_persist():
            return None

        monkeypatch.setattr("lumbergh.session_attention.persist", _noop_persist)
        return sent

    def test_manual_refresh_is_held(self, babysit, monkeypatch):
        babysit.start("port", None, "t")
        sent = self._wire(babysit, monkeypatch, ["issue-792", "issue-804"])
        assert asyncio.run(babysit.refresh("port")) == (babysit.HELD, ["issue-792", "issue-804"])
        assert sent == [], "nothing may reach a session that is supervising live workers"

    def test_the_sentinel_path_is_held_too(self, babysit, monkeypatch):
        # Even the session asking for it: a REFRESH-READY left in the transcript tail from
        # its last cycle must not fire while this cycle's workers are still running.
        babysit.start("port", None, "t")
        monkeypatch.setattr(babysit, "last_agent_text", lambda _s: "⟳ REFRESH-READY")
        sent = self._wire(babysit, monkeypatch, ["issue-792"])
        assert asyncio.run(babysit.on_idle("port")) == babysit.HELD
        assert sent == []

    def test_a_delivered_worker_does_not_hold_the_refresh(self, babysit, monkeypatch):
        # Landing delivered work and refreshing is the normal cycle — only workers still
        # running (or stuck, and needing their overseer's context to answer) hold it.
        babysit.start("port", None, "t")
        sent = self._wire(babysit, monkeypatch, [])
        assert asyncio.run(babysit.refresh("port")) == (babysit.REFRESHED, [])
        assert sent == [(PORT_REF, "/clear"), (PORT_REF, "/fleet-start")]
