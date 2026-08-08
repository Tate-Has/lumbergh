"""`lb brief write` is the only way a Bill without filesystem access can file a brief."""

import io

import pytest

from lumbergh.agent_cli import brief as brief_cli
from lumbergh.agent_cli import main as lb


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


@pytest.fixture
def sent(monkeypatch):
    captured = {}

    def fake_request(method, path, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kw.get("json")
        name = kw.get("json", {}).get("name", "x")
        return _Resp(
            {"path": f"/home/j/.config/lumbergh/bill/briefs/{name}.md", "name": name, "bytes": 12}
        )

    monkeypatch.setattr(brief_cli, "_request", fake_request)
    return captured


@pytest.fixture
def piped(monkeypatch):
    def pipe(text):
        monkeypatch.setattr("sys.stdin", io.StringIO(text))

    return pipe


def test_brief_write_sends_the_slug_and_prints_the_server_side_path(sent, piped, capsys):
    piped("# Task: x\n")

    rc = brief_cli.run(["write"], {"--name": "flaky-login"})

    assert rc == 0
    assert sent["method"] == "POST"
    assert sent["path"] == "/api/bill/brief"
    assert sent["json"] == {"name": "flaky-login", "body": "# Task: x\n"}
    assert "/bill/briefs/flaky-login.md" in capsys.readouterr().out


def test_brief_write_reads_the_body_from_a_file(sent, tmp_path):
    body = tmp_path / "b.md"
    body.write_text("# Task: from a file\n")

    assert brief_cli.run(["write"], {"--name": "flaky-login", "--file": str(body)}) == 0
    assert sent["json"]["body"] == "# Task: from a file\n"


def test_brief_write_treats_a_dash_as_stdin(sent, piped):
    piped("# Task: piped\n")
    assert brief_cli.run(["write"], {"--name": "flaky-login", "--file": "-"}) == 0
    assert sent["json"]["body"] == "# Task: piped\n"


@pytest.mark.parametrize("slug", ["../escape", "sub/w", "Flaky_Login"])
def test_brief_write_refuses_a_bad_slug_before_calling_the_server(slug, monkeypatch, capsys):
    monkeypatch.setattr(
        brief_cli, "_request", lambda *_a, **_kw: pytest.fail("a bad slug reached the server")
    )
    assert brief_cli.run(["write"], {"--name": slug}) == 2
    assert "slug" in capsys.readouterr().out


def test_brief_write_requires_a_name(monkeypatch, capsys):
    monkeypatch.setattr(
        brief_cli, "_request", lambda *_a, **_kw: pytest.fail("a nameless brief reached the server")
    )
    assert brief_cli.run(["write"], {}) == 2
    assert "--name" in capsys.readouterr().out


def test_brief_write_refuses_an_empty_body(monkeypatch, piped, capsys):
    monkeypatch.setattr(
        brief_cli, "_request", lambda *_a, **_kw: pytest.fail("an empty brief reached the server")
    )
    piped("   \n")
    assert brief_cli.run(["write"], {"--name": "flaky-login"}) == 2
    assert "empty" in capsys.readouterr().out


def test_brief_write_says_where_to_pipe_from_when_stdin_is_a_terminal(monkeypatch, capsys):
    """Without this it blocks on a tty read and looks like a hung command."""

    class _Tty(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr("sys.stdin", _Tty("would block"))
    assert brief_cli.run(["write"], {"--name": "flaky-login"}) == 2
    assert "--file" in capsys.readouterr().out


def test_brief_write_reports_a_missing_file_without_calling_the_server(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(
        brief_cli, "_request", lambda *_a, **_kw: pytest.fail("a missing file reached the server")
    )
    rc = brief_cli.run(["write"], {"--name": "x", "--file": str(tmp_path / "nope.md")})
    assert rc == 2
    assert "nope.md" in capsys.readouterr().out


def test_brief_needs_a_subcommand(capsys):
    assert brief_cli.run([], {"--name": "x"}) == 2
    assert "write" in capsys.readouterr().out


def test_brief_surfaces_a_server_refusal(monkeypatch, piped, capsys):
    piped("x")
    monkeypatch.setattr(
        brief_cli,
        "_request",
        lambda *_a, **_kw: _Resp(
            {"detail": {"stage": "name", "error": "no", "help": "fix it"}}, 400
        ),
    )
    assert brief_cli.run(["write"], {"--name": "flaky-login"}) == 1
    out = capsys.readouterr().out
    assert "no" in out
    assert "fix it" in out


@pytest.mark.usefixtures("sent")
def test_the_printed_path_is_what_spawn_wants(piped, capsys):
    """`lb spawn` sends ``brief_path`` and the *server* opens it, so the path this prints
    has to be the server's — pasteable into `lb spawn --brief` from any host."""
    piped("# Task: x\n")
    brief_cli.run(["write"], {"--name": "flaky-login"})
    printed = dict(
        line.split(": ", 1) for line in capsys.readouterr().out.splitlines() if ": " in line
    )
    assert printed["path"] == "/home/j/.config/lumbergh/bill/briefs/flaky-login.md"


def test_lb_dispatches_brief(monkeypatch, piped, capsys):
    piped("x")
    monkeypatch.setattr(
        brief_cli, "_request", lambda *_a, **_kw: _Resp({"path": "/p.md", "name": "n", "bytes": 1})
    )
    assert lb.main(["brief", "write", "--name", "flaky-login"]) == 0
    assert "/p.md" in capsys.readouterr().out
