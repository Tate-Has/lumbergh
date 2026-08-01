"""Git assembly engine for ``lb land``.

Assembles a run's member branches onto a base by cherry-picking each member's
commits into an EPHEMERAL worktree — never the user's main checkout — then
smoke-tests and (only on explicit go) single-pushes ``batch-<run>`` onto the base.
"""

import subprocess
import tempfile
from pathlib import Path

from lumbergh import worktrees


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def _commits_ahead(repo: Path, base_ref: str, branch: str) -> list[str]:
    r = _git(repo, "rev-list", "--reverse", f"{base_ref}..{branch}")
    if r.returncode != 0:
        return []
    return [line for line in r.stdout.split() if line]


def assemble(repo: Path, run_id: str, base: str, member_branches: list[str]) -> dict:
    """Cherry-pick each member branch onto a fresh batch branch in a temp worktree."""
    base_ref = f"origin/{base}"
    batch = f"batch-{run_id}"

    fetch = _git(repo, "fetch", "origin", base)
    if fetch.returncode != 0:
        return {"ok": False, "stage": "fetch", "error": fetch.stderr.strip()}

    worktree = Path(tempfile.mkdtemp(prefix=f"lb-{batch}-"))
    add = _git(repo, "worktree", "add", "--force", "-B", batch, str(worktree), base_ref)
    if add.returncode != 0:
        worktree.rmdir()
        return {"ok": False, "stage": "worktree", "error": add.stderr.strip()}

    # Link the repo's gitignored deps (.venv, node_modules, .env, …) into the assembly
    # worktree exactly as `lb spawn`/`worktree create` do, so `[land] smoke` runs against a
    # usable checkout. Links only — `post_create` is for a workspace a human/agent develops
    # in and could be slow/interactive; assembly is throwaway.
    cfg = worktrees.parse_worktree_config(repo)
    worktrees.apply_links(repo, worktree, worktrees.plan_links(repo, worktree, cfg))

    picked: dict[str, list[str]] = {}
    for branch in member_branches:
        commits = _commits_ahead(repo, base_ref, branch)
        for commit in commits:
            cp = _git(worktree, "cherry-pick", commit)
            if cp.returncode != 0:
                _git(worktree, "cherry-pick", "--abort")
                cleanup_assembly(repo, worktree, batch)
                return {
                    "ok": False,
                    "stage": "cherry-pick",
                    "branch": branch,
                    "commit": commit,
                    "error": cp.stderr.strip(),
                }
        picked[branch] = commits

    return {"ok": True, "worktree": str(worktree), "batch": batch, "picked": picked}


def batch_exists(repo: Path, batch_branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", batch_branch).returncode == 0


def head_sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def stale_members(
    repo: Path, base: str, batch_branch: str, member_branches: list[str]
) -> list[str]:
    """Member branches whose commits are not all represented (by patch-id) in the
    batch branch — the worker moved since the batch was assembled, so landing the
    batch as-is would silently drop that worker's newer commits. ``git cherry``
    marks each ``base..branch`` commit ``+`` when no patch-equivalent is in the
    batch; any ``+`` means the branch has work the batch never picked up."""
    base_ref = f"origin/{base}"
    moved = []
    for branch in member_branches:
        r = _git(repo, "cherry", batch_branch, branch, base_ref)
        if r.returncode != 0 or any(line.startswith("+") for line in r.stdout.splitlines()):
            moved.append(branch)
    return moved


def checkout_batch(repo: Path, batch_branch: str) -> Path:
    """Throwaway worktree detached at an existing batch branch, with the repo's
    gitignored deps linked in, so ``[land] smoke`` can run against the exact tree
    a ``--push`` is about to land."""
    worktree = Path(tempfile.mkdtemp(prefix=f"lb-{batch_branch}-"))
    _git(repo, "worktree", "add", "--force", "--detach", str(worktree), batch_branch)
    cfg = worktrees.parse_worktree_config(repo)
    worktrees.apply_links(repo, worktree, worktrees.plan_links(repo, worktree, cfg))
    return worktree


def run_smoke(worktree: Path, cmd: str) -> dict:
    # The smoke command is an operator-configured shell string (`[land].smoke` /
    # `--smoke`), like fleet's DEFAULT_SMOKE — shell=True is the intended contract.
    result = subprocess.run(cmd, shell=True, cwd=str(worktree))  # noqa: S602
    return {"ok": result.returncode == 0, "returncode": result.returncode}


def push_batch(cwd: Path, batch_branch: str, base: str) -> dict:
    # cwd is any checkout of the repo — the assembly worktree for a single-shot
    # land, or the main checkout when pushing an already-assembled batch ref.
    r = _git(Path(cwd), "push", "origin", f"{batch_branch}:{base}")
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip()}
    return {"ok": True}


def remove_worktree(repo: Path, worktree: Path | str) -> None:
    """Drop the throwaway assembly worktree but keep its batch branch as a
    durable, inspectable ref — the caller advertises the branch name, so it must
    survive. ``delete_batch`` (or ``cleanup_assembly``) drops the branch later."""
    _git(repo, "worktree", "remove", "--force", str(worktree))


def delete_batch(repo: Path, batch_branch: str) -> bool:
    r = _git(repo, "branch", "-D", batch_branch)
    return r.returncode == 0


def cleanup_assembly(repo: Path, worktree: Path | str, batch_branch: str) -> None:
    _git(repo, "worktree", "remove", "--force", str(worktree))
    _git(repo, "branch", "-D", batch_branch)
