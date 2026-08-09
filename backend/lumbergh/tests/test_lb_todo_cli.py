"""`lb todo` is how a babysat session reads and ticks off the repo's backlog.

`lb todo next` is the load-bearing verb: the `next` skill branches on its exit code and
feeds the index it prints straight back to `lb todo done`.
"""

from pathlib import Path

import pytest

from lumbergh.agent_cli import main as lb
from lumbergh.agent_cli import todo as todo_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _todo(text, done=False, description=None):
    return {"text": text, "done": done, "description": description}


@pytest.fixture
def server(monkeypatch):
    """A fake server whose todo list the test sets, recording what the CLI sent."""
    state = {"todos": [], "calls": []}

    def fake_request(method, path, **kw):
        state["calls"].append({"method": method, "path": path, **kw})
        if path == "/api/bill/todos":
            return _Resp({"todos": state["todos"]})
        if path == "/api/bill/todos/add":
            item = _todo(kw["json"]["text"], description=kw["json"].get("description"))
            state["todos"].append(item)
            return _Resp({"todo": item, "index": len(state["todos"])})
        if path == "/api/bill/todos/done":
            item = state["todos"][kw["json"]["index"] - 1]
            item["done"] = True
            return _Resp({"todo": item, "index": kw["json"]["index"]})
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(todo_cli, "_request", fake_request)
    return state


def test_list_numbers_every_item_and_shows_done_state(server, capsys):
    server["todos"] = [_todo("shipped", done=True), _todo("still to do")]

    assert todo_cli.run([], {}) == 0

    out = capsys.readouterr().out
    assert "1,true,shipped" in out
    assert "2,false," in out
    assert "still to do" in out


@pytest.mark.usefixtures("server")
def test_list_says_so_when_the_backlog_is_empty(capsys):
    assert todo_cli.run([], {}) == 0
    assert "no todos" in capsys.readouterr().out


def test_next_prints_the_first_undone_item_with_its_index(server, capsys):
    server["todos"] = [_todo("done already", done=True), _todo("the real next", description="why")]

    assert todo_cli.run(["next"], {}) == 0

    out = capsys.readouterr().out
    assert "index: 2" in out
    assert "the real next" in out
    assert "why" in out


def test_next_exits_1_with_no_output_when_nothing_is_undone(server, capsys):
    """The skill branches on the exit code rather than parsing, so this is the contract."""
    server["todos"] = [_todo("all done", done=True)]

    assert todo_cli.run(["next"], {}) == 1
    assert capsys.readouterr().out.strip() == ""


@pytest.mark.usefixtures("server")
def test_next_exits_1_on_an_empty_backlog(capsys):
    assert todo_cli.run(["next"], {}) == 1
    assert capsys.readouterr().out.strip() == ""


def test_done_sends_the_index_the_agent_was_given(server, capsys):
    server["todos"] = [_todo("a"), _todo("b")]

    assert todo_cli.run(["done", "2"], {}) == 0

    call = server["calls"][-1]
    assert call["path"] == "/api/bill/todos/done"
    assert call["json"]["index"] == 2
    assert "b" in capsys.readouterr().out


def test_done_requires_a_number(server, capsys):
    assert todo_cli.run(["done", "second"], {}) == 2
    assert not server["calls"]
    assert "number" in capsys.readouterr().out


def test_done_requires_an_index_at_all(server):
    assert todo_cli.run(["done"], {}) == 2
    assert not server["calls"]


def test_add_appends_the_text(server, capsys):
    assert todo_cli.run(["add", "write the thing"], {}) == 0

    assert server["calls"][-1]["json"]["text"] == "write the thing"
    assert "write the thing" in capsys.readouterr().out


def test_add_requires_text(server):
    assert todo_cli.run(["add"], {}) == 2
    assert not server["calls"]


def test_repo_defaults_to_the_cwd(server):
    todo_cli.run([], {})
    assert server["calls"][-1]["params"]["repo"] == str(Path.cwd().resolve())


def test_explicit_repo_wins(server):
    todo_cli.run([], {"--repo": "~"})
    assert server["calls"][-1]["params"]["repo"] == str(Path.home().resolve())


def test_a_server_refusal_is_surfaced_with_its_help(monkeypatch, capsys):
    monkeypatch.setattr(
        todo_cli,
        "_request",
        lambda *_a, **_kw: _Resp(
            {"detail": {"stage": "index", "error": "no todo 9", "help": "run `lb todo`"}}, 400
        ),
    )

    assert todo_cli.run(["done", "9"], {}) == 1
    out = capsys.readouterr().out
    assert "no todo 9" in out
    assert "run `lb todo`" in out


def test_unknown_subcommand_is_refused(server):
    assert todo_cli.run(["finish", "1"], {}) == 2
    assert not server["calls"]


def test_lb_dispatches_todo(server, capsys):
    server["todos"] = [_todo("via lb main")]
    assert lb.main(["todo"]) == 0
    assert "via lb main" in capsys.readouterr().out
