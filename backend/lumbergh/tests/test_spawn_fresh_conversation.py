"""A spawned worker must start a brand-new conversation.

`lb spawn` on a name/branch whose worktree path had been used before resumed the old
agent — the teardown log named the mechanism outright (`claude --continue`) — and the
resumed agent replayed its two-day-old `DELIVERED:` line as if it were fresh work.
"""

from pathlib import Path

import pytest

from lumbergh import providers
from lumbergh.routers import bill


def test_provider_fresh_launch_never_resumes_a_prior_conversation():
    for key in providers.PROVIDERS:
        assert "--continue" not in providers.get_launch_command(key, fresh=True)


def test_default_launch_still_resumes_for_a_human_reattaching():
    assert "--continue" in providers.get_launch_command("claude-code")


@pytest.fixture
def spawnable(monkeypatch, tmp_path):
    """Everything `bill.spawn` touches, stubbed down to the launch command it chooses."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    brief = tmp_path / "brief.md"
    brief.write_text("do the thing")
    workdir = tmp_path / "wt"
    workdir.mkdir()

    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict, raising=False)
    monkeypatch.setattr("lumbergh.routers.settings.get_settings", dict, raising=False)
    monkeypatch.setattr(bill.worktrees, "read_delivery_mode", lambda _r: "commit")
    monkeypatch.setattr(bill.worktrees, "create", lambda *_a, **_k: {"path": str(workdir)})
    monkeypatch.setattr(bill, "_store_session", lambda **_k: None)
    monkeypatch.setattr(
        bill, "_deliver_brief", lambda *_a, **_k: type("D", (), {"delivered": True, "note": None})()
    )

    launches: list[str] = []
    monkeypatch.setattr(
        bill,
        "create_tmux_session",
        lambda _n, _wd, launch_command: launches.append(launch_command),
    )
    monkeypatch.setattr(
        bill,
        "create_tmux_window",
        lambda _s, _n, _wd, launch_command: launches.append(launch_command),
    )
    return repo, brief, launches


def test_spawn_launches_a_fresh_agent_not_a_resumed_one(spawnable):
    repo, brief, launches = spawnable
    bill.spawn(
        bill.SpawnBody(
            repo=str(repo),
            branch="scout-585",
            kind="scout",
            brief_path=str(brief),
            agent_provider="claude-code",
        )
    )
    assert launches == ["claude"]


def test_window_spawn_also_launches_a_fresh_agent(spawnable, monkeypatch):
    repo, brief, launches = spawnable
    monkeypatch.setattr(bill, "list_session_windows", lambda _s: [])
    bill.spawn(
        bill.SpawnBody(
            repo=str(repo),
            branch="scout-585",
            kind="scout",
            brief_path=str(brief),
            agent_provider="claude-code",
            into="port",
        )
    )
    assert launches == ["claude"]


def test_brief_resolution_is_untouched(tmp_path):
    assert Path(bill._resolve_brief(str(tmp_path / "x.md"))).is_absolute()
