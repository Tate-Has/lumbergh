"""Every `lb` command and flag Bill's instructions promise him must actually exist.

Bill runs on a cheap local model that follows ``AGENTS.md`` literally, so a promise the
CLI doesn't keep is not a documentation nit — it is a stall loop. The bundle was written
against the *intended* CLI and drifted from the shipped one more than once (a relative
``--brief`` the server couldn't resolve, an OUTCOME column ``--wait`` never filled, a
``--help`` nothing implemented, paths with no column to read them from). This is the
cheap, loud guard against the next instance.
"""

import re

import pytest

from lumbergh import bill as bill_bundle
from lumbergh.agent_cli import fleet as fleet_cli
from lumbergh.agent_cli import main as lb
from lumbergh.agent_cli import worktree as worktree_cli

_INVOCATION = re.compile(r"`(lb\b[^`]*)`", re.DOTALL)
_PLACEHOLDER = re.compile(r"^[<\[]")


def _invocations(text: str) -> list[list[str]]:
    """Every backtick-quoted `lb ...` invocation in the bundle, as token lists."""
    return [span.split() for span in _INVOCATION.findall(text)]


def _flag_names(tokens: list[str]) -> list[str]:
    """The flags an invocation names, with the usage notation stripped off.

    ``[--new]`` and ``--timeout <s>]`` are both just ``--new`` / ``--timeout`` as far as
    the parser is concerned.
    """
    names = []
    for token in tokens:
        bare = token.lstrip("[").rstrip("]").rstrip(",")
        if bare.startswith("--"):
            names.append(bare)
    return names


@pytest.fixture(params=["professional", "lumbergh"])
def rendered(request):
    return bill_bundle.render(request.param)


def test_every_documented_lb_command_exists(rendered):
    for tokens in _invocations(rendered):
        command = tokens[1] if len(tokens) > 1 else ""
        if _PLACEHOLDER.match(command):
            continue
        assert command in lb.FLAGS, (
            f"AGENTS.md tells Bill to run `lb {command}`, which `lb` does not implement"
        )


def test_every_documented_lb_flag_exists_for_its_command(rendered):
    for tokens in _invocations(rendered):
        command = tokens[1] if len(tokens) > 1 else ""
        if _PLACEHOLDER.match(command) or command not in lb.FLAGS:
            continue
        for flag in _flag_names(tokens):
            if flag == "--help":
                continue
            assert flag in lb.FLAGS[command], (
                f"AGENTS.md tells Bill to pass `{flag}` to `lb {command}`, "
                f"which accepts only {sorted(lb.FLAGS[command])}"
            )


def test_every_documented_worktree_subcommand_exists(rendered):
    for tokens in _invocations(rendered):
        if len(tokens) < 3 or tokens[1] != "worktree":
            continue
        sub = tokens[2]
        if _PLACEHOLDER.match(sub):
            continue
        assert sub in worktree_cli.SUBCOMMANDS, (
            f"AGENTS.md tells Bill to run `lb worktree {sub}`, "
            f"which dispatches only {list(worktree_cli.SUBCOMMANDS)}"
        )


def test_the_documented_fleet_columns_are_the_columns_lb_prints(rendered):
    """AGENTS.md names the columns Bill reads values out of — including the two paths he
    must never type from memory. A column named there but not rendered means he is
    reading a value that isn't on screen."""
    header = re.search(r"`(TASK[^`]*)`", rendered, re.DOTALL)
    assert header, "AGENTS.md no longer shows Bill the fleet table's columns"
    documented = [column.strip().lower() for column in header.group(1).split("·")]
    assert documented == fleet_cli._COLS


def test_help_is_available_for_every_command(capsys):
    """AGENTS.md points Bill at ``lb <command> --help`` when he is unsure of syntax; a
    weak model that can self-serve syntax does not stall. Every command must answer it
    without issuing a request."""
    for command in lb.FLAGS:
        argv = [command, "--help"] if command else ["--help"]
        assert lb.main(argv) == 0, f"`lb {command} --help` did not succeed"
        out = capsys.readouterr().out
        assert out.startswith("lb"), f"`lb {command} --help` printed {out!r}"


def test_help_never_reaches_the_server(monkeypatch):
    """`lb fleet --help` used to issue a real long-poll request and print a table."""

    def fail_on_request(*_a, **_kw):
        pytest.fail("--help issued a request")

    monkeypatch.setattr(lb, "_request", fail_on_request)
    assert lb.main(["fleet", "--help"]) == 0
    assert lb.main(["spawn", "--help"]) == 0


def test_every_command_has_a_usage_line():
    assert set(lb._COMMAND_HELP) == set(lb.FLAGS)
