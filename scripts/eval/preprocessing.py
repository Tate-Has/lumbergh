"""Diff preprocessing: filtering lockfiles, generated files, and truncation."""

import re

LOCKFILE_PATTERNS = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "Pipfile.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
    "Cargo.lock",
    "go.sum",
]

GENERATED_PATTERNS = [
    r"\.min\.js$",
    r"\.min\.css$",
    r"^dist/",
    r"^build/",
    r"^vendor/",
    r"\.bundle\.js$",
]

# Files to prioritize (source code first)
SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".rb",
    ".swift",
    ".kt",
    ".c",
    ".cpp",
    ".h",
}

_DIFF_FILE_HEADER = re.compile(r"^diff --git a/(.*?) b/(.*?)$", re.MULTILINE)


def _split_hunks(diff: str) -> list[tuple[str, str]]:
    """Split a unified diff into (filename, hunk_text) pairs."""
    parts = _DIFF_FILE_HEADER.split(diff)
    # parts[0] is before first match, then groups of (a_path, b_path, content)
    hunks = []
    i = 1
    while i < len(parts) - 2:
        a_path = parts[i]
        b_path = parts[i + 1]
        content = parts[i + 2]
        filename = b_path if b_path != "/dev/null" else a_path
        header = f"diff --git a/{a_path} b/{b_path}"
        hunks.append((filename, header + content))
        i += 3
    return hunks


def _rejoin_hunks(hunks: list[tuple[str, str]]) -> str:
    return "".join(text for _, text in hunks)


def filter_lockfiles(diff: str) -> str:
    """Remove hunks for lockfiles."""
    hunks = _split_hunks(diff)
    filtered = [
        (f, t)
        for f, t in hunks
        if not any(f.endswith(lock) for lock in LOCKFILE_PATTERNS)
    ]
    return _rejoin_hunks(filtered)


def filter_generated(diff: str) -> str:
    """Remove hunks for generated/minified files."""
    hunks = _split_hunks(diff)
    compiled = [re.compile(p) for p in GENERATED_PATTERNS]
    filtered = [
        (f, t) for f, t in hunks if not any(p.search(f) for p in compiled)
    ]
    return _rejoin_hunks(filtered)


def prioritize_source(diff: str) -> str:
    """Reorder hunks: source code first, then config/docs."""
    hunks = _split_hunks(diff)
    source = []
    other = []
    for filename, text in hunks:
        ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        if ext in SOURCE_EXTENSIONS:
            source.append((filename, text))
        else:
            other.append((filename, text))
    return _rejoin_hunks(source + other)


def truncate(diff: str, max_chars: int = 8000) -> str:
    """Truncate diff to max_chars, preferring to cut from the end."""
    if len(diff) <= max_chars:
        return diff
    return diff[:max_chars] + "\n\n... [truncated]"


def extract_diff_metadata(diff: str) -> str:
    """Extract file list and line stats from a diff, returned as a text summary."""
    hunks = _split_hunks(diff)
    files = []
    total_added = 0
    total_removed = 0
    for filename, text in hunks:
        added = text.count("\n+") - text.count("\n+++")
        removed = text.count("\n-") - text.count("\n---")
        total_added += added
        total_removed += removed
        files.append(filename)
    dirs = set()
    for f in files:
        parts = f.split("/")
        if len(parts) > 1:
            dirs.add(parts[0])
    lines = [
        f"Files changed ({len(files)}): {', '.join(files)}",
        f"Lines: +{total_added} -{total_removed}",
        f"Top-level dirs: {', '.join(sorted(dirs)) or 'root'}",
    ]
    return "\n".join(lines)


def suggest_scope(diff: str) -> str:
    """Heuristically suggest a scope from file paths in the diff."""
    hunks = _split_hunks(diff)
    files = [f for f, _ in hunks]
    if not files:
        return ""

    # Check if all files are in one area
    areas = set()
    for f in files:
        parts = f.split("/")
        if "frontend" in parts or "src/components" in "/".join(parts):
            areas.add("ui")
        elif "backend" in parts or "routers" in "/".join(parts):
            areas.add("api")
        elif "test" in parts or "e2e" in "/".join(parts) or f.endswith("_test.py") or f.endswith(".test.ts"):
            areas.add("test")
        elif f.endswith(".md"):
            areas.add("docs")
        elif f.endswith(".json") or f.endswith(".toml") or f.endswith(".yaml") or f.endswith(".yml"):
            areas.add("config")

    if len(areas) == 1:
        return areas.pop()
    return ""


# Registry for config-driven pipeline
PREPROCESSORS = {
    "filter_lockfiles": filter_lockfiles,
    "filter_generated": filter_generated,
    "prioritize_source": prioritize_source,
}


def apply_pipeline(
    diff: str,
    steps: list[str] | None = None,
    max_chars: int = 8000,
) -> str:
    """Apply named preprocessing steps, then always truncate."""
    for step_name in steps or []:
        fn = PREPROCESSORS.get(step_name)
        if fn:
            diff = fn(diff)
    return truncate(diff, max_chars)
