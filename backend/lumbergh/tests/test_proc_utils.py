import os
import subprocess
import sys
import time
from pathlib import Path

from lumbergh import proc_utils


def _spawn_orphan(cwd: Path, pidfile: Path, *, ignore_sigterm: bool = False) -> int:
    """A process the way a leaked test server really exists: reparented to init, so
    nothing in this process tree owns it. `setsid --fork` exits immediately, leaving
    the interpreter running with no relation to us."""
    guard = "import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); " * ignore_sigterm
    script = f"import os, time; {guard}open({str(pidfile)!r}, 'w').write(str(os.getpid())); time.sleep(300)"
    subprocess.run(
        ["setsid", "--fork", sys.executable, "-c", script],
        cwd=str(cwd),
        check=True,
    )
    for _ in range(200):
        if pidfile.exists() and pidfile.read_text():
            return int(pidfile.read_text())
        time.sleep(0.02)
    raise AssertionError("orphan never reported its pid")


def _alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def _reap_orphan(pid: int) -> None:
    if _alive(pid):
        os.kill(pid, 9)


def _wait_gone(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return False


def test_processes_under_finds_a_process_whose_cwd_is_in_the_tree(tmp_path):
    tree = tmp_path / "wt"
    (tree / "sub").mkdir(parents=True)
    pid = _spawn_orphan(tree / "sub", tmp_path / "pid")
    try:
        assert pid in {p["pid"] for p in proc_utils.processes_under(tree)}
    finally:
        _reap_orphan(pid)


def test_processes_under_ignores_processes_outside_the_tree(tmp_path):
    tree = tmp_path / "wt"
    tree.mkdir()
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    pid = _spawn_orphan(elsewhere, tmp_path / "pid")
    try:
        assert pid not in {p["pid"] for p in proc_utils.processes_under(tree)}
    finally:
        _reap_orphan(pid)


def test_processes_under_never_reports_the_caller_or_its_ancestors(tmp_path):
    tree = tmp_path / "wt"
    tree.mkdir()
    os.chdir(tree)
    try:
        found = {p["pid"] for p in proc_utils.processes_under(tree)}
        assert os.getpid() not in found
        assert os.getppid() not in found
    finally:
        os.chdir("/")


def test_processes_under_skips_our_own_children(tmp_path):
    """GitPython leaves a `git cat-file --batch` running with its cwd in every repo it
    touches. Those are the reaper's own, and they go when it does."""
    tree = tmp_path / "wt"
    tree.mkdir()
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"],
        cwd=str(tree),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if Path(f"/proc/{child.pid}/cwd").exists():
                break
            time.sleep(0.02)

        assert child.pid not in {p["pid"] for p in proc_utils.processes_under(tree)}
    finally:
        child.kill()
        child.wait()


def test_kill_processes_under_kills_and_reports_them(tmp_path):
    tree = tmp_path / "wt"
    tree.mkdir()
    pid = _spawn_orphan(tree, tmp_path / "pid")
    try:
        killed = proc_utils.kill_processes_under(tree)

        assert [k["pid"] for k in killed] == [pid]
        assert killed[0]["signal"] == "SIGTERM"
        assert "python" in killed[0]["cmd"]
        assert _wait_gone(pid)
    finally:
        _reap_orphan(pid)


def test_kill_processes_under_escalates_to_sigkill_when_sigterm_is_ignored(tmp_path):
    tree = tmp_path / "wt"
    tree.mkdir()
    pid = _spawn_orphan(tree, tmp_path / "pid", ignore_sigterm=True)
    try:
        killed = proc_utils.kill_processes_under(tree, grace_seconds=0.5)

        assert [k["pid"] for k in killed] == [pid]
        assert killed[0]["signal"] == "SIGKILL"
        assert _wait_gone(pid)
    finally:
        _reap_orphan(pid)


def test_kill_processes_under_finds_a_process_left_by_an_already_deleted_tree(tmp_path):
    """The worst case in the wild: the worktree is gone and the server is still up, its
    cwd reading `… (deleted)`. Reaping a registry ghost still has to clear it."""
    tree = tmp_path / "wt"
    tree.mkdir()
    pid = _spawn_orphan(tree, tmp_path / "pid")
    try:
        (tree).rmdir()

        killed = proc_utils.kill_processes_under(tree)

        assert [k["pid"] for k in killed] == [pid]
        assert _wait_gone(pid)
    finally:
        _reap_orphan(pid)


def test_processes_under_spares_the_caller_and_everything_that_spawned_it(tmp_path):
    """`lb worktree reap .` is run from inside the doomed worktree: killing the shell
    that asked for the reap is worse than the leak the sweep exists to clear."""
    tree = tmp_path / "wt"
    tree.mkdir()
    caller = _spawn_orphan(tree, tmp_path / "pid")
    try:
        assert caller not in {p["pid"] for p in proc_utils.processes_under(tree, protect=[caller])}
        assert proc_utils.kill_processes_under(tree, protect=[caller]) == []
        assert _alive(caller)
    finally:
        _reap_orphan(caller)
