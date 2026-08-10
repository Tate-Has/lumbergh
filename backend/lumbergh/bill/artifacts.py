"""Bill's briefs and reports, as things a Bill without filesystem access can read.

A brief is prose and stays prose. A report carries a small contracted header above its
prose — ``actionable``, ``done_when``, ``open_questions``, ``confidence`` — so a remote
Bill can triage a directory of findings without fetching every body, and so the one thing
a scout learned that nobody else can supply (what it needed and could not determine)
arrives as a list rather than buried in a paragraph.

The header is rendered here rather than trusted from the scout, for the same reason
``append_preference`` formats its own bullet: the shape has to hold however weak the model
driving it is. Reading is deliberately more forgiving than writing — a report with no
header still returns its prose, because losing a scout's findings to a malformed field
would be far worse than losing the field.

There is no YAML dependency and this is not a YAML parser. It renders and reads back
exactly the four keys below; anything else in the block is ignored.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

from lumbergh.bill import home

CONFIDENCE = ("high", "medium", "low")
KINDS = ("briefs", "reports")

_MARKER = "---"
_LIST_ITEM = re.compile(r"^\s+-\s+(.*)$")
_KEY_VALUE = re.compile(r"^([a-z_]+):\s*(.*)$")

# A scalar safe to write bare. Anything else is double-quoted, which matters more than it
# looks: a `done_when` is a sentence a model wrote, and sentences contain colons.
_BARE_SAFE = re.compile(r"^[A-Za-z0-9][^:#\n]*$")


def dir_for(kind: str) -> Path:
    return home() / kind


def validate(actionable: bool | None, done_when: str | None, confidence: str | None) -> str | None:
    """Why this report may not be filed, or ``None`` if it may.

    ``done_when`` is required only when the report is actionable: a "nothing to do here"
    report has no done-when, and requiring one would only teach the model to invent it.
    """
    if actionable is None:
        return "actionable is required — say whether this report describes work to do"
    if confidence not in CONFIDENCE:
        return f"confidence must be one of {', '.join(CONFIDENCE)}"
    if actionable and not (done_when or "").strip():
        return "done_when is required for an actionable report — say what finishing looks like"
    return None


def _scalar(text: str) -> str:
    collapsed = " ".join(text.split())
    if _BARE_SAFE.match(collapsed):
        return collapsed
    escaped = collapsed.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _unscalar(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return text


def render_frontmatter(
    actionable: bool,
    done_when: str | None,
    open_questions: list[str] | None,
    confidence: str,
) -> str:
    lines = [_MARKER, f"actionable: {'true' if actionable else 'false'}"]
    if done_when and done_when.strip():
        lines.append(f"done_when: {_scalar(done_when)}")
    questions = [q for q in (open_questions or []) if q.strip()]
    if questions:
        lines.append("open_questions:")
        lines.extend(f"  - {_scalar(q)}" for q in questions)
    else:
        lines.append("open_questions: []")
    lines += [f"confidence: {confidence}", _MARKER, ""]
    return "\n".join(lines)


def _split(text: str) -> tuple[list[str], str] | None:
    """The frontmatter lines and the prose after them, or ``None`` if there is no block.

    A lone opening marker is not a block: a report whose prose starts with a horizontal
    rule must come back whole, not silently swallowed.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != _MARKER:
        return None
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == _MARKER)
    except StopIteration:
        return None
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return lines[1:end], body


def parse(text: str) -> tuple[dict, str]:
    """``(frontmatter, body)``. A text with no readable block is all body."""
    split = _split(text)
    if split is None:
        return {}, text
    lines, body = split

    frontmatter: dict = {}
    collecting: list[str] | None = None
    for line in lines:
        item = _LIST_ITEM.match(line)
        if item is not None and collecting is not None:
            collecting.append(_unscalar(item.group(1)))
            continue
        collecting = None
        match = _KEY_VALUE.match(line)
        if match is None:
            continue
        key, raw = match.group(1), match.group(2).strip()
        if key == "actionable":
            frontmatter[key] = raw == "true"
        elif key in ("done_when", "confidence"):
            frontmatter[key] = _unscalar(raw)
        elif key == "open_questions":
            frontmatter[key] = []
            if raw in ("", "[]"):
                collecting = frontmatter[key] if raw == "" else None
    return frontmatter, body


def write_report(
    name: str,
    body: str,
    *,
    actionable: bool,
    done_when: str | None,
    open_questions: list[str] | None,
    confidence: str,
) -> Path:
    path = dir_for("reports") / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    header = render_frontmatter(actionable, done_when, open_questions, confidence)
    path.write_text(f"{header}\n{body.lstrip()}")
    return path


def _stat(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.stem,
        "path": str(path),
        "bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
    }


def listing(kind: str) -> list[dict]:
    """Every artifact of ``kind``, by name. Reports carry their header, so a reader can
    triage the whole directory in one call and fetch only the bodies that matter."""
    directory = dir_for(kind)
    if not directory.is_dir():
        return []
    rows = []
    for path in sorted(directory.glob("*.md")):
        row = _stat(path)
        if kind == "reports":
            row.update(parse(path.read_text())[0])
        rows.append(row)
    return rows


def read_artifact(kind: str, name: str) -> dict:
    """One artifact. Absent is a normal answer, not an error — a home that was never
    materialized, or a slug the caller guessed, is a thing to report, not to raise on."""
    path = dir_for(kind) / f"{name}.md"
    if not path.is_file():
        return {"name": name, "path": str(path), "exists": False, "body": ""}
    text = path.read_text()
    if kind != "reports":
        return {**_stat(path), "exists": True, "body": text}
    frontmatter, body = parse(text)
    return {**_stat(path), "exists": True, "frontmatter": frontmatter, "body": body}
