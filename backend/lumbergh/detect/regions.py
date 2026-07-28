"""Pure region extraction for the manifest detection engine.

A region selects which lines of the captured pane a rule sees. All text is
ANSI-stripped and right-trimmed, with trailing blank lines dropped, so slicing
matches the historical ``idle_detector._recent_lines`` behavior exactly.
"""

import re

_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[PX^_][^\x1b]*\x1b\\")
_RECENT_LINES_RE = re.compile(r"^recent_lines\((\d+)\)$")

_DEFAULT_RECENT = 15


def _clean_lines(content: str) -> list[str]:
    lines = [_ANSI_PATTERN.sub("", line).rstrip() for line in content.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def extract(region: str, content: str, osc_title: str) -> list[str]:
    if region == "osc_title":
        title = _ANSI_PATTERN.sub("", osc_title).strip()
        return [title] if title else []

    if region == "recent":
        return _clean_lines(content)[-_DEFAULT_RECENT:]

    match = _RECENT_LINES_RE.match(region)
    if match:
        n = int(match.group(1))
        return _clean_lines(content)[-n:] if n else []

    return []
