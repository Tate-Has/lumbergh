from collections.abc import Callable

from lumbergh.targets import (
    Window,
    discover_target_refs,
    discover_targets,
    format_target,
    parse_target,
    window_labels,
    window_runs_agent,
)

# Ground-truth signal is the pane's process tree, not its on-screen text.
AGENT = {"bash", "claude"}
AGENT_WITH_SUBPROCESS = {"bash", "claude", "uv", "python"}  # agent shelled out to a tool
SHELL = {"bash"}


def _windows(*specs: tuple[str, set[str]]) -> list[Window]:
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


def _discover(session: str, *specs: tuple[str, set[str]], workers: set[str] | None = None):
    return discover_targets(
        [session],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
        worker_targets=workers or set(),
    )


def test_parse_bare_session_has_no_window():
    assert parse_target("port") == ("port", None)


def test_parse_session_window_splits_on_first_colon():
    assert parse_target("port:fleet-644") == ("port", "fleet-644")


def test_format_round_trips_parse():
    assert format_target("port", None) == "port"
    assert format_target("port", "fleet-644") == "port:fleet-644"


def test_window_runs_agent_detects_agent_process():
    assert window_runs_agent(AGENT) is True


def test_window_runs_agent_detects_agent_running_a_subprocess():
    assert window_runs_agent(AGENT_WITH_SUBPROCESS) is True


def test_window_runs_agent_rejects_plain_shell():
    assert window_runs_agent(SHELL) is False


def test_labels_use_window_names_when_unique():
    windows = _windows(("fleet-643", AGENT), ("fleet-644", AGENT))
    assert window_labels(windows) == {"@1": "fleet-643", "@2": "fleet-644"}


def test_labels_fall_back_to_index_for_shared_names():
    windows = _windows(("claude", AGENT), ("claude", AGENT))
    assert window_labels(windows) == {"@1": "1", "@2": "2"}


def test_labels_keep_the_unique_name_beside_a_shared_one():
    windows = _windows(("claude", AGENT), ("claude", AGENT), ("server", SHELL))
    assert window_labels(windows) == {"@1": "1", "@2": "2", "@3": "server"}


def test_labels_fall_back_to_index_for_an_empty_name():
    """tmux permits `rename-window ""`, and an empty label would format to the bare
    session — a target that addresses whichever window happens to be active."""
    assert window_labels(_windows(("", AGENT), ("server", SHELL))) == {"@1": "1", "@2": "server"}


def test_session_identity_is_its_first_agent_window():
    assert _discover("port", ("claude", AGENT)) == ["port"]


def test_extra_agent_windows_never_change_the_session_identity():
    """The overnight outage: opening a second Claude in `port` to look at something
    renamed the session's identity, so a babysit keyed to `port` pointed at nothing.
    A window nobody registered as work is the user's business, not supervision's."""
    assert _discover("port", ("claude", AGENT), ("claude", AGENT)) == ["port"]


def test_non_agent_windows_never_change_the_session_identity():
    assert _discover("port", ("claude", AGENT), ("server", SHELL), ("notes", SHELL)) == ["port"]


def test_identity_skips_a_leading_non_agent_window():
    assert _discover("port", ("server", SHELL), ("claude", AGENT)) == ["port"]


def test_session_with_no_agent_at_all_yields_nothing():
    assert _discover("port", ("server", SHELL)) == []


def test_discover_finds_agent_with_no_visible_ui_marker():
    """Regression: a busy/compact-mode agent shows no box-frame chrome in its
    pane, but its process is alive — it must still be discovered. This is the
    port/issue-668 drop-out that made sessions vanish from `lb`."""
    assert _discover("issue-668", ("win0", AGENT)) == ["issue-668"]


def test_registered_worker_windows_expand_to_their_own_targets():
    """A fleet batch: every window was spawned as a worker and registered as one, so the
    container has no agent of its own and each window is supervised in its own right."""
    result = _discover(
        "port-821-839",
        ("838", AGENT),
        ("839", AGENT),
        workers={"port-821-839:838", "port-821-839:839"},
    )
    assert result == ["port-821-839:838", "port-821-839:839"]


def test_a_session_keeps_its_identity_beside_its_registered_workers():
    """An overseer that spawned window workers into its own session is still itself."""
    result = _discover(
        "port",
        ("claude", AGENT),
        ("issue-841", AGENT),
        workers={"port:issue-841"},
    )
    assert result == ["port", "port:issue-841"]


def test_a_registered_worker_window_is_never_mistaken_for_the_session_agent():
    """Window 1 spawned as a worker does not make the container promptable as itself —
    prompting it would type into that worker's pane."""
    result = _discover("batch", ("838", AGENT), workers={"batch:838"})
    assert result == ["batch:838"]


def test_refs_point_at_the_window_that_is_the_target():
    """Identity is the session name; the ref is what tmux is actually handed. Without
    this a bare name reaches tmux and resolves to whichever window is *selected*."""
    specs = (("claude", AGENT), ("issue-841", AGENT))
    refs = discover_target_refs(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
        worker_targets={"port:issue-841"},
    )
    assert refs == {"port": "@1", "port:issue-841": "@2"}


def test_refs_point_at_the_first_agent_window_when_earlier_ones_are_idle_shells():
    specs = (("server", SHELL), ("claude", AGENT))
    refs = discover_target_refs(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),
    )
    assert refs == {"port": "@2"}


def test_discover_never_asks_tmux_about_a_formatted_target():
    """Lookups go by window id, so no window name — duplicated, colon-bearing, or
    otherwise awkward — can make a live agent unaddressable."""
    specs = (("odd:name", AGENT), ("also odd", AGENT))
    refs = discover_target_refs(
        ["port"],
        list_windows=lambda _s: _windows(*specs),
        pane_commands=_pane_commands(*specs),  # raises if asked about "port:odd:name"
        worker_targets={"port:odd:name", "port:also odd"},
    )
    assert refs == {"port:odd:name": "@1", "port:also odd": "@2"}
