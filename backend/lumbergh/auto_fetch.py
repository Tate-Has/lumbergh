"""Keeping ``origin/*`` honest for the session you are looking at.

Nothing else fetches on a schedule, so remote-tracking refs are only ever as
fresh as your last visit to the git view — which makes the graph, the "just my
work" filter and the ahead/behind counts quietly wrong on a repo other people
are pushing to.

This fetches in the background for sessions with recent interest, under three
constraints. It is rate limited per repository, so a session and its worktrees
cost one fetch between them rather than one each. It gives up quickly, because
a hung remote must never occupy a worker thread indefinitely. And it backs off
hard on failure, so an unreachable remote is retried on a lengthening interval
instead of every cycle — an offline laptop should cost nothing.
"""

import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 300.0
# A remote that is unreachable, slow, or asking for credentials we will never
# supply gets retried on a lengthening interval, capped here.
MAX_BACKOFF_SECONDS = 1800.0
FETCH_TIMEOUT_SECONDS = 20.0


def repo_key(workdir: Path) -> str | None:
    """Identify the repository behind a worktree, so siblings share a cooldown."""
    result = subprocess.run(
        ["git", "-C", str(workdir), "rev-parse", "--git-common-dir"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    common = result.stdout.strip()
    if not common:
        return None
    path = Path(common)
    if not path.is_absolute():
        path = (Path(workdir) / path).resolve()
    return str(path)


def has_remote(workdir: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(workdir), "remote"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def fetch(workdir: Path) -> bool:
    """Fetch and prune, returning whether it worked.

    ``GIT_TERMINAL_PROMPT=0`` is already set process-wide, so a remote wanting
    credentials fails fast rather than blocking on a prompt nobody can answer.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(workdir), "fetch", "--prune", "--quiet"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.info(f"Auto-fetch timed out for {workdir}")
        return False
    if result.returncode != 0:
        logger.info(f"Auto-fetch failed for {workdir}: {result.stderr.strip()[:200]}")
        return False
    return True


class FetchSchedule:
    """When each repository is next allowed to be fetched."""

    def __init__(self, cooldown: float = DEFAULT_COOLDOWN_SECONDS):
        self.cooldown = cooldown
        self._next_due: dict[str, float] = {}
        self._backoff: dict[str, float] = {}

    def due(self, key: str, now: float) -> bool:
        """A repo never fetched before is due immediately."""
        if self.cooldown <= 0:
            return False
        return now >= self._next_due.get(key, 0.0)

    def succeeded(self, key: str, now: float) -> None:
        self._backoff.pop(key, None)
        self._next_due[key] = now + self.cooldown

    def failed(self, key: str, now: float) -> None:
        previous = self._backoff.get(key, 0.0)
        backoff = min(max(previous * 2, self.cooldown), MAX_BACKOFF_SECONDS)
        self._backoff[key] = backoff
        self._next_due[key] = now + backoff

    def forget(self, key: str) -> None:
        self._next_due.pop(key, None)
        self._backoff.pop(key, None)

    def now(self) -> float:
        return time.monotonic()
