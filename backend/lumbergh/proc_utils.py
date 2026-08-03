"""Find and kill processes still running inside a directory tree.

A worker that starts a test server leaves it running when its window dies, and
reaping the worktree out from under it produces a process whose binary is alive
but whose tree is gone — still holding a port and a shared-DB connection, and
running code nobody can read anymore. Teardown asks here who those are.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

PROC = Path("/proc")


def _ancestors(pid: int) -> set[int]:
    seen: set[int] = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            stat = (PROC / str(pid) / "stat").read_text()
        except OSError:
            break
        # "<pid> (<comm>) <state> <ppid> …" — comm can contain spaces and parens,
        # so split after the last ')'.
        try:
            pid = int(stat[stat.rindex(")") + 1 :].split()[1])
        except (ValueError, IndexError):
            break
    return seen


def _is_own_descendant(pid: int) -> bool:
    """Ours already, so not a leak: GitPython keeps a `git cat-file --batch` per repo
    with its cwd inside the worktree, and those die with the process that spawned them."""
    return os.getpid() in _ancestors(pid)


def _command_of(pid: int) -> str:
    try:
        raw = (PROC / str(pid) / "cmdline").read_bytes()
    except OSError:
        raw = b""
    cmd = " ".join(raw.decode("utf-8", "replace").split("\0")).strip()
    if cmd:
        return cmd
    try:
        return (PROC / str(pid) / "comm").read_text().strip()
    except OSError:
        return "?"


def _is_under(path: Path | None, root: Path) -> bool:
    if path is None:
        return False
    return path == root or root in path.parents


def _resolved(pid: int, name: str) -> Path | None:
    """The target of /proc/<pid>/{cwd,exe}, with the kernel's " (deleted)" suffix
    stripped — a process outliving its worktree is exactly the case we must catch."""
    try:
        target = os.readlink(PROC / str(pid) / name)
    except OSError:
        return None
    return Path(target.removesuffix(" (deleted)"))


def processes_under(root: Path, *, protect: Iterable[int] = ()) -> list[dict]:
    """Processes whose working directory or executable lives under ``root``.

    Deliberately not matched on command-line arguments: `git -C <worktree> …` run
    from elsewhere would match, and reap itself runs those. A linked `.venv` is a
    symlink out of the tree, so an interpreter borrowed from the parent repo
    resolves outside ``root`` and is left alone.

    ``protect`` spares those pids and everything that spawned them. The caller
    belongs there: reaping is routinely run from inside the doomed worktree, and a
    sweep that takes out the operator's own shell is worse than the leak it fixes.
    """
    root = root.resolve()
    skip = _ancestors(os.getpid())
    for pid in protect:
        skip |= _ancestors(pid)
    found = []
    for entry in PROC.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in skip:
            continue
        cwd, exe = _resolved(pid, "cwd"), _resolved(pid, "exe")
        if (_is_under(cwd, root) or _is_under(exe, root)) and not _is_own_descendant(pid):
            found.append({"pid": pid, "cmd": _command_of(pid)})
    return sorted(found, key=lambda p: p["pid"])


def kill_processes_under(
    root: Path, *, grace_seconds: float = 3.0, protect: Iterable[int] = ()
) -> list[dict]:
    """SIGTERM everything under ``root``, SIGKILL whatever is still up after the
    grace period, and report every pid — a silent kill is its own trap."""
    targets = processes_under(root, protect=protect)
    if not targets:
        return []

    for proc in targets:
        proc["signal"] = "SIGTERM"
        try:
            os.kill(proc["pid"], signal.SIGTERM)
        except OSError as exc:
            proc["signal"] = "none"
            proc["error"] = str(exc)

    deadline = time.monotonic() + grace_seconds
    pending = [p for p in targets if p["signal"] == "SIGTERM"]
    while pending and time.monotonic() < deadline:
        pending = [p for p in pending if _alive(p["pid"])]
        if pending:
            time.sleep(0.05)

    for proc in pending:
        proc["signal"] = "SIGKILL"
        try:
            os.kill(proc["pid"], signal.SIGKILL)
        except OSError as exc:
            proc["error"] = str(exc)
    return targets


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
