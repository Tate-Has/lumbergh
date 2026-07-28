"""Priority-ordered evaluation of manifest rules against a pane snapshot.

Returns the manifest state string of the highest-priority matching rule, or
None when nothing matches or a veto (state="none") wins. The engine deals only
in manifest vocabulary; the idle_detector shim maps the result to SessionState.
"""

import logging

from lumbergh.detect.manifest import Manifest, Predicate, Rule
from lumbergh.detect.regions import extract

logger = logging.getLogger(__name__)

_FOOTER_MARKERS = ("shift+tab to cycle", "esc to interrupt", "? for shortcuts")


def _predicate_passes(predicate: Predicate, blob_lower: str, lines: list[str]) -> bool:
    if any(term.lower() not in blob_lower for term in predicate.contains):
        return False
    if predicate.regex is not None and not predicate.regex.search(blob_lower):
        return False
    if predicate.line_regex is not None and not any(
        predicate.line_regex.search(line) for line in lines
    ):
        return False
    if predicate.any and not any(
        _predicate_passes(clause, blob_lower, lines) for clause in predicate.any
    ):
        return False
    return not any(_predicate_passes(clause, blob_lower, lines) for clause in predicate.not_)


def _footer_blocks(content: str, osc_title: str) -> bool:
    tail = extract("recent_lines(3)", content, osc_title)
    tail_lower = "\n".join(tail).lower()
    return any(marker in tail_lower for marker in _FOOTER_MARKERS)


def _rule_matches(rule: Rule, content: str, osc_title: str) -> bool:
    if rule.not_footer and _footer_blocks(content, osc_title):
        return False
    lines = extract(rule.region, content, osc_title)
    blob_lower = "\n".join(lines).lower()
    return _predicate_passes(rule.predicate, blob_lower, lines)


def classify(content: str, osc_title: str, manifests: list[Manifest]) -> str | None:
    try:
        rules = [rule for manifest in manifests for rule in manifest.rules]
        for rule in sorted(rules, key=lambda r: r.priority, reverse=True):
            if _rule_matches(rule, content, osc_title):
                return None if rule.state == "none" else rule.state
        return None
    except Exception as exc:
        logger.warning("Detection engine error, deferring to quiescence: %s", exc)
        return None
