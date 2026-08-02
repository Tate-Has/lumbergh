"""A timeout must say which kind it was.

`lb fleet --wait` holds a long poll open, and Lumbergh gets restarted underneath it
routinely. "the server went away" and "the request ran out of time" demand opposite
responses, so an undifferentiated traceback is a standing misdiagnosis trap.
"""

import httpx
import pytest

from lumbergh.agent_cli import main


@pytest.fixture
def transport_fails(monkeypatch):
    """Break the transport itself, not one module's `_request` binding — every command
    reaches the server through `httpx.request`, whichever module holds the wrapper."""

    def _install(exc):
        def _boom(*_a, **_kw):
            raise exc

        monkeypatch.setattr(httpx, "request", _boom)

    return _install


def test_read_timeout_while_the_server_is_gone_says_the_server_went_away(
    monkeypatch, transport_fails, capsys
):
    transport_fails(httpx.ReadTimeout("timed out"))
    monkeypatch.setattr(main, "_server_is_reachable", lambda: False)

    rc = main.main(["fleet", "--wait"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "went away" in out
    assert "restart" in out


def test_read_timeout_against_a_live_server_says_the_request_ran_out_of_time(
    monkeypatch, transport_fails, capsys
):
    transport_fails(httpx.ReadTimeout("timed out"))
    monkeypatch.setattr(main, "_server_is_reachable", lambda: True)

    rc = main.main(["fleet", "--wait"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "still up" in out
    assert "--timeout" in out


@pytest.mark.parametrize(
    "exc", [httpx.ConnectError("refused"), httpx.ReadTimeout("t"), httpx.ConnectTimeout("t")]
)
def test_transport_failures_never_reach_the_user_as_a_traceback(
    monkeypatch, transport_fails, exc, capsys
):
    transport_fails(exc)
    monkeypatch.setattr(main, "_server_is_reachable", lambda: False)

    assert main.main(["fleet"]) == 1
    assert "Traceback" not in capsys.readouterr().out


def test_server_is_reachable_reports_false_when_nothing_answers(monkeypatch):
    def _boom(*_a, **_kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", _boom)

    assert main._server_is_reachable() is False
