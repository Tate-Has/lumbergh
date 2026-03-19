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
