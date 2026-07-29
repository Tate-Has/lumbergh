"""First-class worktree lifecycle: config, location, linking, registry, reconcile, reap.

Git's `worktree list` is the source of truth for existence; this module keeps a
thin metadata overlay (see registry helpers) reconciled on read.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from git.exc import GitCommandError
from tinydb import Query

from lumbergh.db_utils import get_worktrees_db
from lumbergh.git_utils import (
    count_unpushed_commits,
    get_porcelain_status,
    get_repo,
    get_worktree_container_path,
    list_worktrees,
    sanitize_branch_for_path,
)
from lumbergh.git_utils import (
    create_worktree as _git_create_worktree,
)
from lumbergh.git_utils import (
    remove_worktree as _git_remove_worktree,
)
from lumbergh.providers import DEFAULT_PROVIDER

# NOTE: do not import get_settings here. The core stays free of the settings/router
# layer; the caller passes `global_base_dir` in (the router reads the setting).

LinkMode = Literal["symlink", "copy"]
DEFAULT_LINKS = [".venv", "node_modules", ".env", ".env.local", ".direnv"]


@dataclass(frozen=True)
class LinkSpec:
    path: str
    mode: LinkMode = "symlink"


@dataclass
class WorktreeProjectConfig:
    links: list[LinkSpec] | None = None  # None => auto-detect
    post_create: list[str] = field(default_factory=list)
    base_dir: str | None = None


def _coerce_link(entry: object) -> LinkSpec:
    if isinstance(entry, str):
        return LinkSpec(path=entry, mode="symlink")
    if isinstance(entry, dict) and "path" in entry:
        mode = entry.get("mode", "symlink")
        if mode not in ("symlink", "copy"):
            raise ValueError(f"invalid link mode: {mode!r}")
        return LinkSpec(path=str(entry["path"]), mode=mode)
    raise ValueError(f"invalid link entry: {entry!r}")


def parse_worktree_config(repo: Path) -> WorktreeProjectConfig:
    dotfile = repo / ".lumbergh.toml"
    if not dotfile.is_file():
        return WorktreeProjectConfig()
    data = tomllib.loads(dotfile.read_text())
    wt = data.get("worktree", {})
    raw_links = wt.get("links")
    links = [_coerce_link(e) for e in raw_links] if raw_links is not None else None
    return WorktreeProjectConfig(
        links=links,
        post_create=list(wt.get("post_create", [])),
        base_dir=wt.get("base_dir"),
    )


def resolve_worktree_dir(
    repo: Path, branch: str, cfg: WorktreeProjectConfig, global_base_dir: str | None
) -> Path:
    leaf = sanitize_branch_for_path(branch)
    base = cfg.base_dir or global_base_dir
    if base:
        return Path(base).expanduser() / repo.name / leaf
    return get_worktree_container_path(repo) / leaf


def _is_git_ignored(repo: Path, rel: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", rel],
        capture_output=True,
    )
    return result.returncode == 0


def plan_links(repo: Path, worktree: Path, cfg: WorktreeProjectConfig) -> list[LinkSpec]:
    specs = cfg.links if cfg.links is not None else [LinkSpec(p) for p in DEFAULT_LINKS]
    planned: list[LinkSpec] = []
    for spec in specs:
        src = repo / spec.path
        dst = worktree / spec.path
        if not src.exists():
            continue
        if dst.exists() or dst.is_symlink():
            continue
        if not _is_git_ignored(repo, spec.path):
            continue
        planned.append(spec)
    return planned


def _reflink_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["cp", "-a", "--reflink=auto", str(src), str(dst)], capture_output=True)
    if result.returncode != 0:
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy2(src, dst)


def apply_links(repo: Path, worktree: Path, specs: list[LinkSpec]) -> list[dict]:
    applied: list[dict] = []
    for spec in specs:
        src = (repo / spec.path).resolve()
        dst = worktree / spec.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if spec.mode == "symlink":
            dst.symlink_to(src)
        else:
            _reflink_copy(src, dst)
        applied.append({"path": spec.path, "mode": spec.mode})
    return applied


def _key(path: Path) -> str:
    return str(Path(path).resolve())


def record_worktree(
    path: Path,
    parent_repo: Path,
    branch: str,
    created_at: str,
    session: str | None = None,
    links_applied: list[dict] | None = None,
    task_intent: str | None = None,
    kind: str | None = None,
    origin: str | None = None,
) -> dict:
    row = {
        "path": _key(path),
        "parent_repo": str(Path(parent_repo).resolve()),
        "branch": branch,
        "created_at": created_at,
        "associated_session": session,
        "links_applied": links_applied or [],
        "task_intent": task_intent,
        "kind": kind,
        "origin": origin,
    }
    db = get_worktrees_db()
    db.upsert(row, Query().path == row["path"])
    return row


def get_entry(path: Path) -> dict | None:
    return get_worktrees_db().get(Query().path == _key(path))


def remove_entry(path: Path) -> None:
    get_worktrees_db().remove(Query().path == _key(path))


def all_entries() -> list[dict]:
    return get_worktrees_db().all()


def _live_session_for(
    worktree: Path, live_sessions: dict[str, dict]
) -> tuple[str | None, str | None]:
    target = _key(worktree)
    for name, meta in live_sessions.items():
        wd = meta.get("workdir")
        if wd and str(Path(wd).resolve()) == target:
            return name, (meta.get("agent_provider") or DEFAULT_PROVIDER)
    return None, None


def reconcile(repo: Path, live_sessions: dict[str, dict]) -> list[dict]:
    git_worktrees = {_key(Path(wt.path)): wt for wt in list_worktrees(repo)}

    for row in all_entries():
        if row["parent_repo"] == _key(repo) and row["path"] not in git_worktrees:
            remove_entry(Path(row["path"]))

    rows: list[dict] = []
    for key, wt in git_worktrees.items():
        if _key(repo) == key:
            continue
        entry = get_entry(Path(wt.path)) or {}
        session, agent = _live_session_for(Path(wt.path), live_sessions)
        rows.append(
            {
                "path": key,
                "repo": repo.name,
                "branch": wt.branch or entry.get("branch"),
                "session": session,
                "agent": agent,
                "state": "active" if session else "orphan",
            }
        )
    return rows


def reconcile_all(live_sessions: dict[str, dict]) -> list[dict]:
    repos = {Path(row["parent_repo"]) for row in all_entries()}
    rows: list[dict] = []
    for repo in repos:
        rows.extend(reconcile(repo, live_sessions))
    return rows


def create(
    repo: Path,
    branch: str,
    *,
    created_at: str,
    create_branch: bool = False,
    base_branch: str | None = None,
    session: str | None = None,
    task_intent: str | None = None,
    global_base_dir: str | None = None,
    kind: str | None = None,
    origin: str | None = None,
) -> dict:
    cfg = parse_worktree_config(repo)
    dest = resolve_worktree_dir(repo, branch, cfg, global_base_dir)
    result = _git_create_worktree(
        repo, branch, worktree_path=dest, create_branch=create_branch, base_branch=base_branch
    )
    if "error" in result:
        return result
    wt = Path(result["path"])
    applied = apply_links(repo, wt, plan_links(repo, wt, cfg))
    for cmd in cfg.post_create:
        subprocess.run(cmd, shell=True, cwd=wt, check=False)  # noqa: S602 - project-configured hook command
    record_worktree(
        wt,
        repo,
        branch,
        created_at,
        session=session,
        links_applied=applied,
        task_intent=task_intent,
        kind=kind,
        origin=origin,
    )
    return {"path": str(wt), "links_applied": applied}


def reap(worktree: Path, *, force: bool = False, rm_branch: bool = False) -> dict:
    if not force:
        if get_porcelain_status(worktree):
            return {"error": "worktree has uncommitted changes", "reason": "dirty"}
        if count_unpushed_commits(worktree) > 0:
            return {"error": "worktree has unpushed commits", "reason": "unpushed"}
    entry = get_entry(worktree)
    parent = Path(entry["parent_repo"]) if entry else parent_repo_of(worktree)
    branch = entry.get("branch") if entry else None
    result = _git_remove_worktree(parent, worktree, force=force)
    if "error" in result:
        return result
    remove_entry(worktree)
    if rm_branch and branch:
        try:
            get_repo(parent).git.branch("-D", branch)
        except GitCommandError:
            pass
    return {"status": "removed", "path": str(worktree)}


def parent_repo_of(worktree: Path) -> Path:
    common = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    git_dir = Path(common)
    if not git_dir.is_absolute():
        git_dir = (worktree / git_dir).resolve()
    return git_dir.parent


def adopt(worktree: Path, created_at: str, session: str | None) -> dict:
    repo = parent_repo_of(worktree)
    branch = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    row = record_worktree(worktree, repo, branch, created_at, session=session)
    return {"status": "adopted", **row}


def unlink_path(worktree: Path, rel: str) -> dict:
    target = worktree / rel
    if not target.is_symlink():
        return {"path": rel, "status": "skipped", "reason": "not a symlink"}
    real = target.resolve()
    target.unlink()
    _reflink_copy(real, target)
    return {"path": rel, "status": "copied"}
