"""Expand `lb batch --briefs` (a directory or a file list) into (brief, stem) pairs."""

from pathlib import Path

from lumbergh.routers.sessions import SESSION_NAME_PATTERN


def enumerate_briefs(paths: list[str]) -> list[tuple[Path, str]]:
    resolved = [Path(p).expanduser() for p in paths]
    if len(resolved) == 1 and resolved[0].is_dir():
        files = sorted(resolved[0].glob("*.md"))
    else:
        files = resolved

    out: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for f in files:
        if not f.is_file():
            raise ValueError(f"brief path does not exist: {f}")
        stem = f.stem
        if not SESSION_NAME_PATTERN.match(stem):
            raise ValueError(
                f"brief filename `{f.name}` yields an illegal worker name `{stem}` "
                "(letters, numbers, underscores, hyphens only)"
            )
        if stem in seen:
            raise ValueError(f"duplicate worker name `{stem}` from {f.name}")
        seen.add(stem)
        out.append((f.resolve(), stem))
    return out
