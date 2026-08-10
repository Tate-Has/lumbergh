"""`lb report` — how a scout files findings a supervisor can act on without reading prose."""

import io
import json

import pytest

from lumbergh.agent_cli import main as lb
from lumbergh.agent_cli import report as report_cli


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
        captured["params"] = kw.get("params")
        name = (kw.get("json") or {}).get("name", "x")
        return _Resp(
            {"path": f"/home/j/.config/lumbergh/bill/reports/{name}.md", "name": name, "bytes": 20}
        )

    monkeypatch.setattr(report_cli, "_request", fake_request)
    return captured


@pytest.fixture
def piped(monkeypatch):
    def pipe(text):
        monkeypatch.setattr("sys.stdin", io.StringIO(text))

    return pipe


def _flags(**overrides):
    flags = {
        "--name": "flaky-login",
        "--actionable": "yes",
        "--done-when": "the retry shim is gone",
        "--confidence": "high",
    }
    flags.update(overrides)
    return {k: v for k, v in flags.items() if v is not None}


def test_write_sends_the_header_fields_with_the_prose(sent, piped, capsys):
    piped("# Findings\n")

    rc = report_cli.run(["write"], _flags(**{"--open-question": ["which env does CI use?"]}))

    assert rc == 0
    assert sent["method"] == "POST"
    assert sent["path"] == "/api/bill/report"
    assert sent["json"] == {
        "name": "flaky-login",
        "body": "# Findings\n",
        "actionable": True,
        "done_when": "the retry shim is gone",
        "open_questions": ["which env does CI use?"],
        "confidence": "high",
    }
    assert "DELIVERED: report flaky-login" in capsys.readouterr().out, (
        "the scout's next move is the contracted final line — say it rather than "
        "assume a model that just filed a report remembers the contract"
    )


def test_write_accepts_several_open_questions(sent, piped):
    piped("prose")
    questions = ["which env does CI use?", "is -x still passed?"]

    report_cli.run(["write"], _flags(**{"--open-question": questions}))

    assert sent["json"]["open_questions"] == questions


def test_write_reads_the_prose_from_a_file(sent, tmp_path):
    body = tmp_path / "r.md"
    body.write_text("# Findings from a file\n")

    rc = report_cli.run(["write"], _flags(**{"--file": str(body)}))

    assert rc == 0
    assert sent["json"]["body"] == "# Findings from a file\n"


@pytest.mark.parametrize(("raw", "expected"), [("yes", True), ("no", False), ("true", True)])
def test_actionable_accepts_the_obvious_spellings(sent, piped, raw, expected):
    piped("prose")
    report_cli.run(["write"], _flags(**{"--actionable": raw, "--done-when": "done"}))
    assert sent["json"]["actionable"] is expected


def test_a_missing_actionable_is_refused_before_any_request(sent, piped, capsys):
    piped("prose")

    rc = report_cli.run(["write"], _flags(**{"--actionable": None}))

    assert rc == 2
    assert sent == {}, "a usage error must not reach the server"
    assert "--actionable" in capsys.readouterr().out


def test_an_unknown_confidence_is_refused_locally(sent, piped, capsys):
    piped("prose")

    rc = report_cli.run(["write"], _flags(**{"--confidence": "certain"}))

    assert rc == 2
    assert sent == {}
    assert "confidence" in capsys.readouterr().out


def test_an_actionable_report_without_a_done_when_is_refused_locally(sent, piped, capsys):
    piped("prose")

    rc = report_cli.run(["write"], _flags(**{"--done-when": None}))

    assert rc == 2
    assert sent == {}
    assert "done_when" in capsys.readouterr().out


def test_a_non_actionable_report_needs_no_done_when(sent, piped):
    piped("prose")

    rc = report_cli.run(["write"], _flags(**{"--actionable": "no", "--done-when": None}))

    assert rc == 0
    assert sent["json"]["actionable"] is False


def test_an_empty_report_is_refused(sent, piped, capsys):
    piped("   \n")

    rc = report_cli.run(["write"], _flags())

    assert rc == 2
    assert sent == {}
    assert "empty" in capsys.readouterr().out


@pytest.fixture
def stored(monkeypatch):
    payload = {
        "name": "flaky-login",
        "path": "/home/j/.config/lumbergh/bill/reports/flaky-login.md",
        "exists": True,
        "frontmatter": {
            "actionable": True,
            "done_when": "the retry shim is gone",
            "open_questions": ["which env does CI use?"],
            "confidence": "high",
        },
        "body": "# Findings\n\nthe shim is dead code\n",
    }
    monkeypatch.setattr(report_cli, "_request", lambda *a, **kw: _Resp(payload))  # noqa: ARG005
    return payload


@pytest.mark.usefixtures("stored")
def test_read_prints_the_header_and_the_prose(capsys):
    rc = report_cli.run(["read", "flaky-login"], {})

    out = capsys.readouterr().out
    assert rc == 0
    assert "confidence: high" in out
    assert "which env does CI use?" in out
    assert "the shim is dead code" in out


def test_read_json_returns_exactly_frontmatter_and_body(stored, capsys):
    rc = report_cli.run(["read", "flaky-login"], {"--json": True})

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {
        "frontmatter": stored["frontmatter"],
        "body": stored["body"],
    }


def test_reading_a_report_that_is_not_there_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(
        report_cli,
        "_request",
        lambda *a, **kw: _Resp({"name": "nope", "path": "/x", "exists": False, "body": ""}),  # noqa: ARG005
    )

    rc = report_cli.run(["read", "nope"], {})

    assert rc == 1, "an empty success would read as a report that was filed blank"
    assert "no report named `nope`" in capsys.readouterr().out


def test_list_shows_the_header_fields_so_a_directory_can_be_triaged_at_once(monkeypatch, capsys):
    monkeypatch.setattr(
        report_cli,
        "_request",
        lambda *a, **kw: _Resp(  # noqa: ARG005
            {
                "reports": [
                    {
                        "name": "a",
                        "actionable": True,
                        "confidence": "high",
                        "open_questions": ["q?"],
                        "modified": "2026-08-10T00:00:00+00:00",
                    }
                ]
            }
        ),
    )

    rc = report_cli.run(["list"], {})

    out = capsys.readouterr().out
    assert rc == 0
    assert "reports[1]{name,actionable,confidence,questions,modified}:" in out
    assert "a,true,high,1," in out


def test_an_unknown_subcommand_is_a_usage_error(capsys):
    assert report_cli.run(["ponder"], {}) == 2
    assert "unknown subcommand" in capsys.readouterr().out


def test_report_is_registered_with_the_parser():
    """Every command needs a flag set, a help line, and a dispatch entry, or `lb report`
    fails at parse time with `unknown command` however good the module is."""
    assert "report" in lb.FLAGS
    assert "report" in lb._COMMAND_HELP
    assert "--open-question" in lb._REPEATABLE_FLAGS["report"]

    command, flags, positional, err = lb._parse(
        ["report", "write", "--name", "x", "--open-question", "a?", "--open-question", "b?"]
    )
    assert err is None
    assert command == "report"
    assert positional == ["write"]
    assert flags["--open-question"] == ["a?", "b?"]
