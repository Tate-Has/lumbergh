"""Git assembly engine for ``lb land``.

Assembles a run's member branches onto a base by cherry-picking each member's
commits into an EPHEMERAL worktree — never the user's main checkout — then
smoke-tests and (only on explicit go) single-pushes ``batch-<run>`` onto the base.
"""

import subprocess
import tempfile
from pathlib import Path


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


def run_smoke(worktree: Path, cmd: str) -> dict:
    # The smoke command is an operator-configured shell string (`[land].smoke` /
    # `--smoke`), like fleet's DEFAULT_SMOKE — shell=True is the intended contract.
    result = subprocess.run(cmd, shell=True, cwd=str(worktree))  # noqa: S602
    return {"ok": result.returncode == 0, "returncode": result.returncode}


def push_batch(worktree: Path, batch_branch: str, base: str) -> dict:
    r = _git(Path(worktree), "push", "origin", f"{batch_branch}:{base}")
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip()}
    return {"ok": True}


def cleanup_assembly(repo: Path, worktree: Path | str, batch_branch: str) -> None:
    _git(repo, "worktree", "remove", "--force", str(worktree))
    _git(repo, "branch", "-D", batch_branch)
