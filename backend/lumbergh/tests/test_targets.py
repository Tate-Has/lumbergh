from lumbergh.targets import (
    discover_targets,
    format_target,
    parse_target,
    select_targets,
    window_runs_agent,
)

CLAUDE_PANE = "\n╭─ Claude Code ─╮\n│ > \n╰──────────────╯\n"
SHELL_PANE = "user@host:~/src$ "


def test_parse_bare_session_has_no_window():
    assert parse_target("port") == ("port", None)


def test_parse_session_window_splits_on_first_colon():
    assert parse_target("port:fleet-644") == ("port", "fleet-644")


def test_format_round_trips_parse():
    assert format_target("port", None) == "port"
    assert format_target("port", "fleet-644") == "port:fleet-644"


def test_single_agent_window_collapses_to_bare_session():
    assert select_targets({"port": ["claude"]}) == ["port"]


def test_multiple_agent_windows_expand_to_targets():
    assert select_targets({"port": ["fleet-644", "fleet-643"]}) == [
        "port:fleet-643",
        "port:fleet-644",
    ]


def test_session_with_no_agent_windows_yields_nothing():
    assert select_targets({"port": []}) == []


def test_window_runs_agent_detects_claude_ui():
    assert window_runs_agent(CLAUDE_PANE) is True


def test_window_runs_agent_rejects_plain_shell():
    assert window_runs_agent(SHELL_PANE) is False


def test_discover_collapses_single_agent_window():
    windows = {"port": ["win0"]}
    panes = {"port": CLAUDE_PANE}  # bare session capture
    result = discover_targets(
        ["port"],
        list_windows=lambda s: windows[s],
        capture=lambda t: panes.get(t, ""),
    )
    assert result == ["port"]


def test_discover_expands_two_agent_windows():
    panes = {"port:fleet-643": CLAUDE_PANE, "port:fleet-644": CLAUDE_PANE}
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: ["fleet-644", "fleet-643"],
        capture=lambda t: panes.get(t, ""),
    )
    assert result == ["port:fleet-643", "port:fleet-644"]


def test_discover_ignores_non_agent_windows():
    panes = {"port:fleet-644": CLAUDE_PANE, "port:logs": SHELL_PANE}
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: ["fleet-644", "logs"],
        capture=lambda t: panes.get(t, ""),
    )
    assert result == ["port"]  # only one agent window → collapses
