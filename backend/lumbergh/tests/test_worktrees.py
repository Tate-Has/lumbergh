import importlib
import subprocess
from pathlib import Path

import pytest

from lumbergh import worktrees


@pytest.fixture
def registry(tmp_path, monkeypatch):
    from tinydb import TinyDB

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    yield db
    db.close()


@pytest.fixture
def worktrees_db(tmp_path, monkeypatch):
    from tinydb import TinyDB

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    yield db
    db.close()


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "t")
    (path / ".gitignore").write_text(".venv/\nnode_modules/\n.env\n")
    (path / "README").write_text("x")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    return path


def test_parse_config_absent_dotfile_yields_autodetect(tmp_path):
    cfg = worktrees.parse_worktree_config(tmp_path)
    assert cfg.links is None
    assert cfg.post_create == []
    assert cfg.base_dir is None


def test_parse_config_reads_links_modes_hooks_and_basedir(tmp_path):
    _write(
        tmp_path / ".lumbergh.toml",
        "[worktree]\n"
        'base_dir = "~/wt"\n'
        'links = [{ path = ".venv", mode = "copy" }, "node_modules"]\n'
        'post_create = ["uv sync"]\n',
    )
    cfg = worktrees.parse_worktree_config(tmp_path)
    assert cfg.base_dir == "~/wt"
    assert cfg.post_create == ["uv sync"]
    assert cfg.links == [
        worktrees.LinkSpec(path=".venv", mode="copy"),
        worktrees.LinkSpec(path="node_modules", mode="symlink"),
    ]


def test_resolve_dir_sibling_default(tmp_path):
    repo = tmp_path / "app"
    repo.mkdir()
    cfg = worktrees.parse_worktree_config(repo)
    out = worktrees.resolve_worktree_dir(repo, "feat/x", cfg, global_base_dir=None)
    assert out == tmp_path / "app-worktrees" / "feat-x"


def test_resolve_dir_global_base_dir(tmp_path):
    repo = tmp_path / "app"
    repo.mkdir()
    cfg = worktrees.parse_worktree_config(repo)
    out = worktrees.resolve_worktree_dir(
        repo, "feat/x", cfg, global_base_dir=str(tmp_path / "central")
    )
    assert out == tmp_path / "central" / "app" / "feat-x"


def test_resolve_dir_dotfile_base_dir_wins_over_global(tmp_path):
    repo = tmp_path / "app"
    repo.mkdir()
    _write(repo / ".lumbergh.toml", f'[worktree]\nbase_dir = "{tmp_path / "proj"}"\n')
    cfg = worktrees.parse_worktree_config(repo)
    out = worktrees.resolve_worktree_dir(
        repo, "feat/x", cfg, global_base_dir=str(tmp_path / "central")
    )
    assert out == tmp_path / "proj" / "app" / "feat-x"


def test_plan_links_autodetect_only_existing_and_ignored(tmp_path):
    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".env").write_text("SECRET=1")
    # node_modules absent -> skipped; README tracked -> never a candidate anyway
    cfg = worktrees.parse_worktree_config(repo)
    wt = tmp_path / "wt"
    wt.mkdir()
    planned = {s.path for s in worktrees.plan_links(repo, wt, cfg)}
    assert planned == {".venv", ".env"}


def test_plan_links_skips_when_already_present_in_worktree(tmp_path):
    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    cfg = worktrees.parse_worktree_config(repo)
    wt = tmp_path / "wt"
    (wt / ".venv").mkdir(parents=True)  # already there
    assert worktrees.plan_links(repo, wt, cfg) == []


def test_apply_links_symlink_and_copy(tmp_path):
    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "marker").write_text("v")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "pkg").write_text("n")
    _write(
        repo / ".lumbergh.toml",
        '[worktree]\nlinks = [{ path = ".venv", mode = "copy" }, "node_modules"]\n',
    )
    cfg = worktrees.parse_worktree_config(repo)
    wt = tmp_path / "wt"
    wt.mkdir()
    applied = worktrees.apply_links(repo, wt, worktrees.plan_links(repo, wt, cfg))
    assert {r["path"]: r["mode"] for r in applied} == {".venv": "copy", "node_modules": "symlink"}
    assert (wt / "node_modules").is_symlink()
    assert not (wt / ".venv").is_symlink()
    assert (wt / ".venv" / "marker").read_text() == "v"


def test_registry_record_get_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    import importlib

    from lumbergh import constants, db_utils

    importlib.reload(constants)
    importlib.reload(db_utils)
    importlib.reload(worktrees)

    wt = tmp_path / "app-worktrees" / "feat-x"
    worktrees.record_worktree(
        wt,
        parent_repo=tmp_path / "app",
        branch="feat/x",
        created_at="2026-07-28T00:00:00Z",
        session="kb-1",
        links_applied=[{"path": ".venv", "mode": "copy"}],
    )
    row = worktrees.get_entry(wt)
    assert row["branch"] == "feat/x"
    assert row["associated_session"] == "kb-1"
    assert row["created_at"] == "2026-07-28T00:00:00Z"
    assert [r["path"] for r in worktrees.all_entries()] == [str(wt.resolve())]
    worktrees.remove_entry(wt)
    assert worktrees.get_entry(wt) is None


def test_reconcile_active_orphan_and_stale_prune(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    import importlib

    from lumbergh import constants, db_utils

    importlib.reload(constants)
    importlib.reload(db_utils)
    importlib.reload(worktrees)

    repo = _init_repo(tmp_path / "app")
    active = tmp_path / "app-worktrees" / "active"
    orphan = tmp_path / "app-worktrees" / "orphan"
    _git(repo, "worktree", "add", "-q", "-b", "active", str(active))
    _git(repo, "worktree", "add", "-q", "-b", "orphan", str(orphan))

    now = "2026-07-28T00:00:00Z"
    worktrees.record_worktree(active, repo, "active", now, session="kb-1")
    worktrees.record_worktree(orphan, repo, "orphan", now, session="kb-gone")
    worktrees.record_worktree(tmp_path / "ghost", repo, "ghost", now)  # not in git -> stale

    live = {"kb-1": {"workdir": str(active), "agent_provider": "claude"}}
    rows = worktrees.reconcile(repo, live)

    by_branch = {r["branch"]: r for r in rows}
    assert by_branch["active"]["state"] == "active"
    assert by_branch["active"]["session"] == "kb-1"
    assert by_branch["active"]["agent"] == "claude"
    assert by_branch["orphan"]["state"] == "orphan"
    assert by_branch["orphan"]["session"] is None
    assert by_branch["orphan"]["agent"] is None
    assert "ghost" not in by_branch
    assert worktrees.get_entry(tmp_path / "ghost") is None  # pruned

    live_no_provider = {"kb-1": {"workdir": str(active), "agent_provider": None}}
    rows_no_provider = worktrees.reconcile(repo, live_no_provider)
    by_branch_no_provider = {r["branch"]: r for r in rows_no_provider}
    from lumbergh.providers import DEFAULT_PROVIDER

    assert by_branch_no_provider["active"]["agent"] == DEFAULT_PROVIDER


def test_count_unpushed_commits_scoped_to_worktree_head(tmp_path):
    from lumbergh.git_utils import count_unpushed_commits

    repo = _init_repo(tmp_path / "app")
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _git(bare, "init", "-q", "--bare")
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")

    worktree_a = tmp_path / "wt-a"
    worktree_b = tmp_path / "wt-b"
    _git(repo, "worktree", "add", "-q", "-b", "a", str(worktree_a))
    _git(repo, "worktree", "add", "-q", "-b", "b", str(worktree_b))
    _git(worktree_a, "push", "-q", "origin", "a")
    _git(worktree_b, "push", "-q", "origin", "b")

    (worktree_b / "extra.txt").write_text("only on b")
    _git(worktree_b, "add", "-A")
    _git(worktree_b, "commit", "-qm", "b-only commit")

    assert count_unpushed_commits(worktree_a) == 0
    assert count_unpushed_commits(worktree_b) == 1


def test_reap_refuses_dirty_then_force_removes(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import constants, db_utils

    importlib.reload(constants)
    importlib.reload(db_utils)
    importlib.reload(worktrees)

    repo = _init_repo(tmp_path / "app")
    now = "2026-07-28T00:00:00Z"
    created = worktrees.create(repo, "feat/x", created_at=now, create_branch=True)
    wt = Path(created["path"])
    (wt / "dirty.txt").write_text("uncommitted")

    refused = worktrees.reap(wt, force=False)
    assert refused["error"]
    assert refused["reason"] == "dirty"
    assert wt.exists()

    forced = worktrees.reap(wt, force=True)
    assert forced["status"] == "removed"
    assert not wt.exists()
    assert worktrees.get_entry(wt) is None


def test_reap_unregistered_worktree_derives_parent_via_git(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import constants, db_utils

    importlib.reload(constants)
    importlib.reload(db_utils)
    importlib.reload(worktrees)

    repo = _init_repo(tmp_path / "app")
    wt = tmp_path / "hand-made-wt"
    _git(repo, "worktree", "add", "-q", "-b", "feat/manual", str(wt))
    assert worktrees.get_entry(wt) is None

    result = worktrees.reap(wt, force=True)

    assert result["status"] == "removed"
    assert not wt.exists()


def test_create_applies_links_and_records(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import constants, db_utils

    importlib.reload(constants)
    importlib.reload(db_utils)
    importlib.reload(worktrees)

    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "m").write_text("v")
    now = "2026-07-28T00:00:00Z"
    created = worktrees.create(repo, "feat/y", created_at=now, create_branch=True, session="kb-9")
    wt = Path(created["path"])
    assert (wt / ".venv").is_symlink()
    entry = worktrees.get_entry(wt)
    assert entry["associated_session"] == "kb-9"
    assert entry["created_at"] == now
    assert {r["path"] for r in entry["links_applied"]} == {".venv"}


def test_session_created_worktree_is_registered(tmp_path, monkeypatch):
    """Creating a worktree session records a registry entry + links (integration seam)."""
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import constants, db_utils
    from lumbergh.routers import sessions

    importlib.reload(constants)
    importlib.reload(db_utils)
    importlib.reload(worktrees)
    importlib.reload(sessions)

    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "m").write_text("v")

    from lumbergh.models import CreateSessionRequest, WorktreeConfig

    body = CreateSessionRequest(
        mode="worktree",
        worktree=WorktreeConfig(parent_repo=str(repo), branch="feat/z", create_branch=True),
    )
    workdir, _parent, _branch = sessions._resolve_worktree_workdir(body)
    assert (Path(workdir) / ".venv").is_symlink()
    assert worktrees.get_entry(Path(workdir)) is not None


@pytest.mark.usefixtures("registry")
def test_record_worktree_persists_kind_and_origin(tmp_path):
    row = worktrees.record_worktree(
        tmp_path / "wt",
        tmp_path / "repo",
        "feat/x",
        "2026-07-28T00:00:00+00:00",
        kind="scout",
        origin="bill",
    )
    assert row["kind"] == "scout"
    assert row["origin"] == "bill"
    assert worktrees.get_entry(tmp_path / "wt")["kind"] == "scout"


@pytest.mark.usefixtures("registry")
def test_record_worktree_defaults_kind_and_origin_to_none(tmp_path):
    row = worktrees.record_worktree(
        tmp_path / "wt", tmp_path / "repo", "feat/x", "2026-07-28T00:00:00+00:00"
    )
    assert row["kind"] is None
    assert row["origin"] is None


@pytest.mark.usefixtures("worktrees_db")
def test_record_worktree_stores_target_and_run(tmp_path):
    row = worktrees.record_worktree(
        path=tmp_path / "wt",
        parent_repo=tmp_path / "repo",
        branch="feat/x",
        created_at="2026-07-30T00:00:00Z",
        target="port:fleet-644",
        run="batch-9",
    )
    assert row["target"] == "port:fleet-644"
    assert row["run"] == "batch-9"


@pytest.mark.usefixtures("worktrees_db")
def test_record_worktree_session_kwarg_back_compat(tmp_path):
    row = worktrees.record_worktree(
        path=tmp_path / "wt2",
        parent_repo=tmp_path / "repo",
        branch="feat/y",
        created_at="2026-07-30T00:00:00Z",
        session="scout-1",
    )
    assert row["target"] == "scout-1"
    assert row["run"] is None
