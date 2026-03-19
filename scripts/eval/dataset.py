"""Extract (diff, message) pairs from git history."""

import json
import subprocess
from pathlib import Path

# Curated commits for stable eval results.
# Selected for breadth: small/medium/large, feat/fix/refactor/chore/docs,
# frontend-only/backend-only/cross-stack.
CURATED_SHAS: list[str] = [
    # Small (1-2 files, <20 lines)
    "c48271d",  # feat(ui): default to markdown preview for .md files
    "12a13de",  # feat(ui): sort diff list by filename path
    "9f154e8",  # chore(frontend): change complexity rule to error
    "4e76134",  # fix(ui): collapse expanded todo on status toggle
    "e1debc2",  # fix(ui): add upgrade command to update banner
    "50ac006",  # feat(ui): navigate to session after creation
    "708e759",  # fix(providers): add fallback for launch commands
    "8a77c98",  # fix(ui): resolve missing syntax highlighting issue
    # Medium (2-7 files)
    "d13ad24",  # fix(ui): focus terminal after sending commands
    "77c13d2",  # feat(ui): focus terminal after clearing input
    "22c98de",  # fix(dev): graceful shutdown timeout
    "f82c545",  # feat(sessions): multiple agent providers (cross-stack)
    "cc6bc6a",  # fix(ui): isolate scratchpad content by session
    "de6eb6c",  # feat(ui): add session name to terminal header
    # Large (8+ files or 100+ lines)
    "1030437",  # fix(diff_cache): include worktree status in hash
    "8fc87b8",  # feat(auth): add password protection and middleware
    "eccbbda",  # refactor(ui): extract git logic into hooks/components
    "3359618",  # feat(git): add ability to delete git branches
]


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _extract_commit(sha: str, repo: Path) -> dict | None:
    """Extract a single commit's data. Returns None if unusable."""
    try:
        info = _run_git(
            ["log", "-1", "--format=%H%x00%an%x00%aI%x00%s%x00%b", sha], repo
        )
    except subprocess.CalledProcessError:
        return None

    parts = info.strip().split("\x00")
    if len(parts) < 4:
        return None

    full_sha = parts[0]
    author = parts[1]
    date = parts[2]
    subject = parts[3]
    body = parts[4] if len(parts) > 4 else ""

    message = subject
    if body.strip():
        message = f"{subject}\n\n{body.strip()}"

    try:
        diff = _run_git(["diff", f"{full_sha}~1..{full_sha}"], repo)
    except subprocess.CalledProcessError:
        return None

    if not diff or len(diff) < 20:
        return None

    # Get numstat
    try:
        stat = _run_git(["diff", "--numstat", f"{full_sha}~1..{full_sha}"], repo)
    except subprocess.CalledProcessError:
        stat = ""

    files_changed = 0
    additions = 0
    deletions = 0
    for line in stat.strip().splitlines():
        parts_stat = line.split("\t")
        if len(parts_stat) == 3:
            try:
                additions += int(parts_stat[0])
                deletions += int(parts_stat[1])
                files_changed += 1
            except ValueError:
                pass

    return {
        "sha": full_sha,
        "original_message": message,
        "author": author,
        "date": date,
        "files_changed": files_changed,
        "additions": additions,
        "deletions": deletions,
        "diff": diff,
        "diff_bytes": len(diff.encode()),
    }


def extract_curated(repo: Path) -> list[dict]:
    """Extract the curated eval dataset."""
    if not CURATED_SHAS:
        raise ValueError(
            "No curated SHAs configured. Either populate CURATED_SHAS "
            "or use extract_dataset() with --max-commits."
        )
    dataset = []
    for sha in CURATED_SHAS:
        entry = _extract_commit(sha, repo)
        if entry:
            dataset.append(entry)
        else:
            print(f"  warning: skipping {sha[:8]} (not found or empty diff)")
    return dataset


def extract_dataset(
    repo: Path,
    *,
    max_commits: int = 50,
    since: str | None = None,
) -> list[dict]:
    """Extract commit entries from git history."""
    log_args = [
        "log",
        "--no-merges",
        f"--max-count={max_commits * 2}",
        "--format=%H",
    ]
    if since:
        log_args.append(f"--since={since}")

    raw = _run_git(log_args, repo)
    shas = [s.strip() for s in raw.strip().splitlines() if s.strip()]

    dataset = []
    for sha in shas:
        entry = _extract_commit(sha, repo)
        if entry:
            dataset.append(entry)
        if len(dataset) >= max_commits:
            break

    return dataset


def save_dataset(dataset: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(dataset, f, indent=2)


def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)
