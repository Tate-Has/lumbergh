"""The `claude` CLI as an AI provider — the one that needs no API key."""

import asyncio

import pytest

from lumbergh.ai.providers import ClaudeCliProvider, get_provider


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0, hang=False):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._hang = hang
        self.killed = False

    async def communicate(self, _input=None):
        if self._hang:
            await asyncio.sleep(3600)
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True

    async def wait(self):
        return self.returncode


def fake_exec(monkeypatch, process, record=None):
    async def create(*cmd, **_kwargs):
        if record is not None:
            record.append(cmd)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)


@pytest.mark.asyncio
async def test_returns_what_claude_printed(monkeypatch):
    fake_exec(monkeypatch, FakeProcess(stdout=b"  Git badge fix\n"))

    assert await ClaudeCliProvider().complete("summarize this") == "Git badge fix"


@pytest.mark.asyncio
async def test_runs_one_shot_with_tools_and_mcp_off(monkeypatch):
    calls = []
    fake_exec(monkeypatch, FakeProcess(stdout=b"ok"), record=calls)

    await ClaudeCliProvider(model="haiku").complete("summarize this")

    cmd = calls[0]
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "summarize this" in cmd
    assert cmd[cmd.index("--model") + 1] == "haiku"
    assert "--strict-mcp-config" in cmd


@pytest.mark.asyncio
async def test_a_failed_run_raises_with_what_claude_said(monkeypatch):
    fake_exec(monkeypatch, FakeProcess(stderr=b"not logged in", returncode=1))

    with pytest.raises(RuntimeError, match="not logged in"):
        await ClaudeCliProvider().complete("summarize this")


@pytest.mark.asyncio
async def test_a_hung_claude_is_killed_rather_than_waited_on(monkeypatch):
    process = FakeProcess(hang=True)
    fake_exec(monkeypatch, process)

    with pytest.raises(RuntimeError, match="timed out"):
        await ClaudeCliProvider(timeout=0.05).complete("summarize this")
    assert process.killed


@pytest.mark.asyncio
async def test_health_is_whether_the_cli_is_there(monkeypatch):
    monkeypatch.setattr("lumbergh.ai.providers.shutil.which", lambda _: "/usr/bin/claude")
    fake_exec(monkeypatch, FakeProcess(stdout=b"2.0.0"))
    assert await ClaudeCliProvider().health_check() is True

    monkeypatch.setattr("lumbergh.ai.providers.shutil.which", lambda _: None)
    assert await ClaudeCliProvider().health_check() is False


def test_the_factory_knows_it():
    provider = get_provider({"provider": "claude_cli", "providers": {"claude_cli": {}}})

    assert isinstance(provider, ClaudeCliProvider)
    assert provider.model == "haiku"
