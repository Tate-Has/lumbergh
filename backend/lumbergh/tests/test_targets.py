from collections.abc import Callable

from lumbergh.targets import (
    Window,
    discover_targets,
    format_target,
    parse_target,
    select_targets,
    window_labels,
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


def _windows(*specs: tuple[str, str]) -> list[Window]:
    """Windows numbered from 1, as tmux hands them out: ``_windows(("claude", AGENT))``."""
    return [Window(f"@{i}", str(i), name) for i, (name, _cmds) in enumerate(specs, start=1)]


def _pane_commands(*specs: tuple[str, set[str]]) -> Callable[[str], set[str]]:
    """A pane lookup that refuses to answer about a window it was never told about.

    Deliberately strict: the previous fakes returned SHELL for anything unrecognized,
    which silently turned "this ref is unresolvable" into "no agent here" — exactly
    the production failure they were supposed to catch.
    """
    by_id = {f"@{i}": cmds for i, (_name, cmds) in enumerate(specs, start=1)}

    def lookup(ref: str) -> set[str]:
        if ref not in by_id:
            raise AssertionError(f"discovery asked about an unknown window ref: {ref!r}")
        return by_id[ref]

    return lookup


def test_labels_use_window_names_when_unique():
    windows = _windows(("fleet-643", AGENT), ("fleet-644", AGENT))
    assert window_labels(windows) == {"@1": "fleet-643", "@2": "fleet-644"}


def test_labels_fall_back_to_index_for_shared_names():
    windows = _windows(("claude", AGENT), ("claude", AGENT))
    assert window_labels(windows) == {"@1": "1", "@2": "2"}


def test_labels_keep_the_unique_name_beside_a_shared_one():
    windows = _windows(("claude", AGENT), ("claude", AGENT), ("server", SHELL))
    assert window_labels(windows) == {"@1": "1", "@2": "2", "@3": "server"}


def test_discover_finds_agent_with_no_visible_ui_marker():
    """Regression: a busy/compact-mode agent shows no box-frame chrome in its
    pane, but its process is alive — it must still be discovered. This is the
    port/issue-668 drop-out that made sessions vanish from `lb`."""
    specs = (("win0", AGENT),)
    result = discover_targets(
        ["issue-668"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
    )
    assert result == ["issue-668"]


def test_discover_collapses_single_agent_window():
    specs = (("win0", AGENT),)
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
    )
    assert result == ["port"]


def test_discover_expands_two_agent_windows():
    specs = (("fleet-644", AGENT), ("fleet-643", AGENT))
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
    )
    assert result == ["port:fleet-643", "port:fleet-644"]


def test_discover_ignores_non_agent_windows():
    specs = (("fleet-644", AGENT), ("logs", SHELL))
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
    )
    assert result == ["port"]  # only one agent window → collapses


def test_discover_survives_two_windows_sharing_a_name():
    """The port outage: two windows both named `claude`, so every `port:claude` ref was
    ambiguous, both windows read as agent-less, and the session left `lb` altogether."""
    specs = (("claude", AGENT), ("claude", AGENT))
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
    )
    assert result == ["port:1", "port:2"]


def test_discover_keeps_a_session_whose_only_agent_shares_its_name():
    specs = (("claude", AGENT), ("claude", SHELL))
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
    )
    assert result == ["port"]


def test_discover_never_asks_tmux_about_a_formatted_target():
    """Lookups go by window id, so no window name — duplicated, colon-bearing, or
    otherwise awkward — can make a live agent unaddressable."""
    specs = (("odd:name", AGENT), ("also odd", AGENT))
    result = discover_targets(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),  # raises if asked about "port:odd:name"
    )
    assert result == ["port:also odd", "port:odd:name"]


def test_labels_fall_back_to_index_for_an_empty_name():
    """tmux permits `rename-window ""`, and an empty label would format to the bare
    session — a target that addresses whichever window happens to be active."""
    assert window_labels(_windows(("", AGENT), ("server", SHELL))) == {"@1": "1", "@2": "server"}
