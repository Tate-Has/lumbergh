"""Markdown export functions for Focus Workspace tasks and archive."""

from collections import defaultdict

STATUSES_ALL = [
    "inbox",
    "today",
    "running",
    "waiting",
    "backlog",
    "in-progress",
    "review",
    "done",
]


def tasks_to_markdown(data: dict) -> str:
    """Convert Focus tasks JSON to markdown format."""
    tasks = data.get("tasks", [])
    md = "# Tasks\n"
    for status in STATUSES_ALL:
        section_tasks = [t for t in tasks if t.get("status") == status]
        md += f"\n## {status}\n"
        for t in section_tasks:
            checked = "[x] " if t.get("completed") else ""
            proj = f"[{t['project']}] " if t.get("project") else ""
            md += f"- {checked}**{proj}{t['title']}** !{t.get('priority', 'med')}\n"
            if t.get("blocker"):
                md += f"  - blocker: {t['blocker']}\n"
            if t.get("check_in_note"):
                md += f"  - check_in: {t['check_in_note']}\n"
            if t.get("completed_date"):
                md += f"  - completed_date: {t['completed_date']}\n"
            if t.get("session_name"):
                md += f"  - session: {t['session_name']}\n"
            if t.get("session_status"):
                md += f"  - session_status: {t['session_status']}\n"
            for st in t.get("subtasks", []):
                mark = "x" if st.get("done") else " "
                md += f"  - [{mark}] {st['text']}\n"
    return md


def archive_to_markdown(data: dict) -> str:
    """Convert Focus archive JSON to markdown format."""
    groups: dict[str, list] = defaultdict(list)
    for t in data.get("tasks", []):
        groups[t.get("archived_date", "unknown")].append(t)

    md = ""
    dates = sorted(groups.keys(), reverse=True)
    for date in dates:
        md += f"## {date}\n"
        for t in groups[date]:
            proj = f"[{t['project']}] " if t.get("project") else ""
            md += f"- [x] **{proj}{t['title']}**"
            if t.get("priority"):
                md += f" !{t['priority']}"
            md += "\n"
            if t.get("blocker"):
                md += f"  - blocker: {t['blocker']}\n"
            if t.get("check_in_note"):
                md += f"  - check_in: {t['check_in_note']}\n"
        md += "\n"

    for n in data.get("notes", []):
        md += f"## Notes -- {n.get('date', 'unknown')}\n"
        md += n.get("content", "") + "\n\n"

    return md
