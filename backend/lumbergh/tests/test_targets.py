from lumbergh.targets import (
    discover_targets,
    format_target,
    parse_target,
    select_targets,
    window_runs_agent,
)

# Ground-truth signal is the pane's process tree, not its on-screen text.
AGENT = {"bash", "claude"}
AGENT_WITH_SUBPROCESS = {"bash", "claude", "uv", "python"}  # agent shelled out to a tool
SHELL = {"bash"}


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


def test_window_runs_agent_detects_agent_process():
    assert window_runs_agent(AGENT) is True


def test_window_runs_agent_detects_agent_running_a_subprocess():
    assert window_runs_agent(AGENT_WITH_SUBPROCESS) is True


def test_window_runs_agent_rejects_plain_shell():
    assert window_runs_agent(SHELL) is False


def test_discover_finds_agent_with_no_visible_ui_marker():
    """Regression: a busy/compact-mode agent shows no box-frame chrome in its
    pane, but its process is alive — it must still be discovered. This is the
    port/issue-668 drop-out that made sessions vanish from `lb`."""
    result = discover_targets(
        ["issue-668"],
        list_windows=lambda _s: ["win0"],
        pane_commands=lambda _t: AGENT,
    )
    assert result == ["issue-668"]


def test_discover_collapses_single_agent_window():
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: ["win0"],
        pane_commands=lambda t: AGENT if t == "port" else SHELL,
    )
    assert result == ["port"]


def test_discover_expands_two_agent_windows():
    commands = {"port:fleet-643": AGENT, "port:fleet-644": AGENT}
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: ["fleet-644", "fleet-643"],
        pane_commands=lambda t: commands.get(t, SHELL),
    )
    assert result == ["port:fleet-643", "port:fleet-644"]


def test_discover_ignores_non_agent_windows():
    commands = {"port:fleet-644": AGENT, "port:logs": SHELL}
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: ["fleet-644", "logs"],
        pane_commands=lambda t: commands.get(t, SHELL),
    )
    assert result == ["port"]  # only one agent window → collapses
