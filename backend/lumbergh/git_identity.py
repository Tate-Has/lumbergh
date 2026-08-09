"""Deciding which refs in a repo are the operator's own work.

On a repo several people push to, a graph of every ref buries the branches you
actually care about. Ownership here is deliberately per-ref and forgiving: a
branch is yours if you appear anywhere in its recent history, so a colleague
landing a small fix on top of your work doesn't disown you.
"""

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK = 5
MAX_LOOKBACK = 50

# Branches you stopped touching months ago are history, not work in progress.
# They are also what pushes live branches off the end of the commit budget, so
# dropping them is what makes the rest of your work visible at all.
DEFAULT_MAX_AGE_DAYS = 90

# Ownership depends only on a ref's tip, so the answer is reusable across the
# background cache's polls. Bounded because tips churn as the fleet works.
_ownership_cache: dict[tuple[str, str, int, frozenset[str], frozenset[str], int], bool] = {}
_OWNERSHIP_CACHE_MAX = 4096


@dataclass(frozen=True)
class Identity:
    """The emails that count as "me", and how far back a ref is searched.

    Falsy when no email could be resolved — callers treat that as "can't tell
    whose work this is" and leave the graph unfiltered rather than showing an
    empty one.
    """

    emails: frozenset[str] = field(default_factory=frozenset)
    lookback: int = DEFAULT_LOOKBACK
    max_age_days: int = DEFAULT_MAX_AGE_DAYS

    def __bool__(self) -> bool:
        return bool(self.emails)


def _git_config_email(cwd: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(cwd), "config", "--get", "user.email"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    email = result.stdout.strip()
    return email or None


def resolve_identity(
    cwd: Path,
    extra_emails: list[str] | tuple[str, ...] = (),
    lookback: int = DEFAULT_LOOKBACK,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> Identity:
    """Resolve who "I" am in ``cwd``: git's own answer plus configured aliases.

    ``max_age_days`` of 0 keeps branches however long ago you abandoned them.
    """
    emails = {e.strip().lower() for e in extra_emails if e and e.strip()}
    configured = _git_config_email(cwd)
    if configured:
        emails.add(configured.lower())

    return Identity(
        frozenset(emails),
        max(1, min(lookback, MAX_LOOKBACK)),
        max(0, max_age_days),
    )


def graph_identity(cwd: Path) -> Identity:
    """The operator's identity for ``cwd``, widened by their configured aliases.

    Imported lazily: settings reaches back into this module for its bounds.
    """
    from lumbergh.routers.settings import get_settings

    settings = get_settings()
    return resolve_identity(
        cwd,
        extra_emails=settings.get("myEmails", []),
        lookback=settings.get("mineLookbackCommits", DEFAULT_LOOKBACK),
        max_age_days=settings.get("mineMaxBranchAgeDays", DEFAULT_MAX_AGE_DAYS),
    )


def owns_ref(
    cwd: Path,
    ref: str,
    tip: str,
    identity: Identity,
    exclude: frozenset[str] = frozenset(),
) -> bool:
    """Whether ``identity`` authored or committed any of ``ref``'s own recent work.

    ``exclude`` holds the trunk refs, and matters more than it looks: without
    it the walk runs straight through the merge-base into shared history, where
    everyone's own commits eventually appear, and every branch in the repo comes
    back "mine".

    Walks ``--first-parent`` so a branch merged in from elsewhere doesn't count
    as work landed *on* this one. Keyed on the tip rather than the ref name, so
    two refs at the same commit share an answer.
    """
    if not identity:
        return False

    key = (
        str(cwd),
        tip,
        identity.lookback,
        identity.emails,
        frozenset(exclude),
        identity.max_age_days,
    )
    cached = _ownership_cache.get(key)
    if cached is not None:
        return cached

    result = subprocess.run(
        [
            "git",
            "-C",
            str(cwd),
            "log",
            "--first-parent",
            f"-{identity.lookback}",
            "--format=%cI%n%ae%n%ce",
            ref,
            "--not",
            *sorted(exclude - {ref}),
        ],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return False

    lines = result.stdout.splitlines()
    commits = [lines[i : i + 3] for i in range(0, len(lines) - 2, 3)]
    owned = any(
        email.strip().lower() in identity.emails for _date, *emails in commits for email in emails
    )
    if owned and identity.max_age_days and commits:
        owned = _within_age(commits[0][0], identity.max_age_days)

    if len(_ownership_cache) >= _OWNERSHIP_CACHE_MAX:
        _ownership_cache.clear()
    _ownership_cache[key] = owned
    return owned


def _within_age(iso_date: str, max_age_days: int) -> bool:
    """Whether the branch's newest commit of its own is recent enough to matter."""
    try:
        when = datetime.fromisoformat(iso_date.strip())
    except ValueError:
        return True
    return (datetime.now(UTC) - when).days <= max_age_days
