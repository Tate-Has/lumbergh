"""A torn-down (or crashed) worker leaves a stored session record behind; teardown
reaps the worktree but not the record, so dead worktree sessions pile up in the
dashboard forever. The reaper removes a stored session only when it is dead (no live
tmux) AND its worktree directory is gone — never a durable session on a real repo."""

from lumbergh.routers.sessions import _is_dead_worktree_orphan


def test_reaps_dead_worktree_session_whose_dir_is_gone(tmp_path):
    meta = {"type": "worktree", "workdir": str(tmp_path / "port-worktrees" / "issue-674")}
    assert _is_dead_worktree_orphan("issue-674", meta, live_names=set()) is True


def test_reaps_dead_batch_container_under_worktrees_path(tmp_path):
    # Batch containers are stored type "direct" but live under a `-worktrees/` dir.
    meta = {"type": "direct", "workdir": str(tmp_path / "port-worktrees" / "673-e2e")}
    assert _is_dead_worktree_orphan("port-661-673", meta, live_names=set()) is True


def test_keeps_worktree_session_that_still_exists(tmp_path):
    wt = tmp_path / "port-worktrees" / "issue-700"
    wt.mkdir(parents=True)
    meta = {"type": "worktree", "workdir": str(wt)}
    assert _is_dead_worktree_orphan("issue-700", meta, live_names=set()) is False


def test_keeps_live_session_even_if_dir_gone(tmp_path):
    meta = {"type": "worktree", "workdir": str(tmp_path / "gone")}
    assert _is_dead_worktree_orphan("issue-674", meta, live_names={"issue-674"}) is False


def test_keeps_durable_direct_session_on_a_real_repo(tmp_path):
    repo = tmp_path / "quotr"
    repo.mkdir()
    meta = {"type": "direct", "workdir": str(repo)}
    assert _is_dead_worktree_orphan("quotr", meta, live_names=set()) is False


def test_keeps_direct_session_whose_repo_is_only_temporarily_gone(tmp_path):
    # A plain repo path (not under `-worktrees/`) that is missing is NOT reaped: it may
    # be a durable session whose repo is transiently unmounted/moved. Only worktree-ish
    # sessions are disposable.
    meta = {"type": "direct", "workdir": str(tmp_path / "src" / "quotr")}
    assert _is_dead_worktree_orphan("quotr", meta, live_names=set()) is False
