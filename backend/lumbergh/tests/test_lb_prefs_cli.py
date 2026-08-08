"""`lb prefs` is how a Bill without filesystem access reads and extends preferences.md."""

import pytest

from lumbergh.agent_cli import main as lb
from lumbergh.agent_cli import prefs as prefs_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


@pytest.fixture
def sent(monkeypatch):
    captured = {}
    replies = {
        "GET": {
            "path": "/home/j/.config/lumbergh/bill/preferences.md",
            "exists": True,
            "body": "# prefs\n\n- 2026-07-28: Small PRs. Reason: phone review.\n",
        },
        "POST": {
            "path": "/home/j/.config/lumbergh/bill/preferences.md",
            "bullet": "- 2026-08-08: Never force-push main. Reason: it is shared.",
        },
    }

    def fake_request(method, path, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kw.get("json")
        return _Resp(replies[method])

    monkeypatch.setattr(prefs_cli, "_request", fake_request)
    return captured


def test_prefs_read_prints_every_line_of_the_file(sent, capsys):
    rc = prefs_cli.run(["read"], {})

    assert rc == 0
    assert sent["method"] == "GET"
    assert sent["path"] == "/api/bill/preferences"
    out = capsys.readouterr().out
    assert "- 2026-07-28: Small PRs. Reason: phone review." in out


def test_prefs_read_says_so_when_the_file_is_not_there_yet(monkeypatch, capsys):
    monkeypatch.setattr(
        prefs_cli,
        "_request",
        lambda *_a, **_kw: _Resp({"path": "/p.md", "exists": False, "body": ""}),
    )
    assert prefs_cli.run(["read"], {}) == 0
    assert "no preferences" in capsys.readouterr().out


def test_prefs_add_sends_the_text_and_the_reason(sent, capsys):
    rc = prefs_cli.run(["add", "Never force-push main."], {"--reason": "it is shared."})

    assert rc == 0
    assert sent["method"] == "POST"
    assert sent["json"] == {"text": "Never force-push main.", "reason": "it is shared."}
    assert "Never force-push main. Reason: it is shared." in capsys.readouterr().out


def test_prefs_add_requires_text(monkeypatch, capsys):
    monkeypatch.setattr(
        prefs_cli,
        "_request",
        lambda *_a, **_kw: pytest.fail("an empty preference reached the server"),
    )
    assert prefs_cli.run(["add"], {"--reason": "why"}) == 2
    assert "text" in capsys.readouterr().out


def test_prefs_add_requires_a_reason(monkeypatch, capsys):
    monkeypatch.setattr(
        prefs_cli, "_request", lambda *_a, **_kw: pytest.fail("a reasonless preference was sent")
    )
    assert prefs_cli.run(["add", "Use uv."], {}) == 2
    assert "--reason" in capsys.readouterr().out


def test_prefs_needs_a_known_subcommand(capsys):
    assert prefs_cli.run(["rewrite"], {}) == 2
    out = capsys.readouterr().out
    assert "read" in out
    assert "add" in out


def test_prefs_has_no_way_to_replace_the_file(capsys):
    """The file is the user's, hand-edited. Append-only is the point, so no verb may write
    it wholesale — not even by accident through an unrecognised subcommand."""
    for sub in ("write", "set", "replace", "clear"):
        assert prefs_cli.run([sub, "anything"], {}) == 2
        capsys.readouterr()


def test_prefs_surfaces_a_server_refusal(monkeypatch, capsys):
    monkeypatch.setattr(
        prefs_cli,
        "_request",
        lambda *_a, **_kw: _Resp(
            {"detail": {"stage": "reason", "error": "no reason given", "help": "pass --reason"}},
            400,
        ),
    )
    assert prefs_cli.run(["add", "Use uv."], {"--reason": "x"}) == 1
    out = capsys.readouterr().out
    assert "no reason given" in out
    assert "pass --reason" in out


def test_lb_dispatches_prefs(monkeypatch, capsys):
    monkeypatch.setattr(
        prefs_cli,
        "_request",
        lambda *_a, **_kw: _Resp({"path": "/p.md", "exists": True, "body": "x"}),
    )
    assert lb.main(["prefs", "read"]) == 0
    assert "x" in capsys.readouterr().out
