"""The dashboard needs each session's place in the fleet tree — is it Bill, a worker,
or a plain session, and which overseer owns a worker — without paying for the transcript
reads and seen/unseen side effects of the full ``fleet`` snapshot. ``_annotate_hierarchy``
derives ``role`` and ``parent`` from the already-built session rows alone."""

from lumbergh.routers.sessions import _annotate_hierarchy


def _annotated(rows):
    _annotate_hierarchy(rows)
    return {r["name"]: r for r in rows}


def test_worker_nests_under_overseer_sharing_its_repo(tmp_path):
    repo = tmp_path / "lumbergh"
    rows = [
        {"name": "lumbergh", "type": "direct", "workdir": str(repo), "worktreeParentRepo": None},
        {
            "name": "port-644",
            "type": "worktree",
            "workdir": str(repo) + "-worktrees/port-644",
            "worktreeParentRepo": str(repo),
        },
    ]
    by_name = _annotated(rows)
    assert by_name["lumbergh"]["role"] == "session"
    assert by_name["port-644"]["role"] == "worker"
    assert by_name["port-644"]["parent"] == "lumbergh"


def test_bill_is_its_own_role_and_never_a_parent(tmp_path):
    rows = [
        {
            "name": "bill",
            "type": "direct",
            "workdir": str(tmp_path / "bill-home"),
            "worktreeParentRepo": None,
        },
    ]
    by_name = _annotated(rows)
    assert by_name["bill"]["role"] == "bill"
    assert by_name["bill"]["parent"] is None


def test_dead_session_on_the_repo_never_outranks_the_live_one(tmp_path):
    """A finished session lingers in the list with ``alive: False`` and the same workdir
    as the session still running there. Whichever sorted later used to win the repo, so a
    worker could name a session that died days ago and drift away from its real parent."""
    repo = tmp_path / "lumbergh"
    rows = [
        {
            "name": "lumbergh",
            "type": "direct",
            "workdir": str(repo),
            "worktreeParentRepo": None,
            "alive": True,
        },
        {
            "name": "zen-verify-htop",
            "type": "direct",
            "workdir": str(repo),
            "worktreeParentRepo": None,
            "alive": False,
        },
        {
            "name": "badge-fix",
            "type": "worktree",
            "workdir": str(repo) + "-worktrees/badge-fix",
            "worktreeParentRepo": str(repo),
            "alive": True,
        },
    ]
    by_name = _annotated(rows)
    assert by_name["badge-fix"]["parent"] == "lumbergh"


def test_dead_session_is_not_an_overseer_even_when_alone_on_the_repo(tmp_path):
    repo = tmp_path / "lumbergh"
    rows = [
        {
            "name": "zen-verify-htop",
            "type": "direct",
            "workdir": str(repo),
            "worktreeParentRepo": None,
            "alive": False,
        },
        {
            "name": "badge-fix",
            "type": "worktree",
            "workdir": str(repo) + "-worktrees/badge-fix",
            "worktreeParentRepo": str(repo),
            "alive": True,
        },
    ]
    by_name = _annotated(rows)
    assert by_name["badge-fix"]["parent"] is None


def test_orphan_worker_has_no_parent_when_its_repo_has_no_live_session(tmp_path):
    repo = tmp_path / "herdr"
    rows = [
        {
            "name": "auth-fix",
            "type": "worktree",
            "workdir": str(repo) + "-worktrees/auth-fix",
            "worktreeParentRepo": str(repo),
        },
    ]
    by_name = _annotated(rows)
    assert by_name["auth-fix"]["role"] == "worker"
    assert by_name["auth-fix"]["parent"] is None


def test_plain_session_is_a_session_with_no_parent(tmp_path):
    rows = [
        {
            "name": "quotr",
            "type": "direct",
            "workdir": str(tmp_path / "quotr"),
            "worktreeParentRepo": None,
        },
    ]
    by_name = _annotated(rows)
    assert by_name["quotr"]["role"] == "session"
    assert by_name["quotr"]["parent"] is None


def test_parent_match_survives_non_normalized_paths(tmp_path):
    repo = tmp_path / "lumbergh"
    repo.mkdir()
    rows = [
        {"name": "lumbergh", "type": "direct", "workdir": str(repo), "worktreeParentRepo": None},
        {
            "name": "port-701",
            "type": "worktree",
            "workdir": str(repo) + "-worktrees/port-701",
            "worktreeParentRepo": str(tmp_path / "." / "lumbergh"),
        },
    ]
    by_name = _annotated(rows)
    assert by_name["port-701"]["parent"] == "lumbergh"
