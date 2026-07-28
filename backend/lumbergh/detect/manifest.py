"""Data model and loader for detection manifests.

A manifest is a TOML file describing priority-ordered rules that classify a
pane snapshot as ``blocked``/``error`` (an override) or ``none`` (a veto that
forces "defer to the quiescence classifier"). Parsing is defensive: a single
bad rule or file is skipped and logged, never fatal.
"""

import logging
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_VALID_STATES = {"blocked", "error", "none"}
_PREDICATE_KEYS = {"contains", "regex", "line_regex", "any", "not"}
_RULE_META_KEYS = {"id", "state", "priority", "region", "not_footer"}


@dataclass
class Predicate:
    contains: list[str] = field(default_factory=list)
    regex: re.Pattern | None = None
    line_regex: re.Pattern | None = None
    any: list["Predicate"] = field(default_factory=list)
    not_: list["Predicate"] = field(default_factory=list)


@dataclass
class Rule:
    id: str
    state: str
    priority: int
    region: str
    not_footer: bool
    predicate: Predicate


@dataclass
class Manifest:
    id: str
    aliases: list[str]
    rules: list[Rule]


def parse_predicate(raw: dict) -> Predicate:
    unknown = set(raw) - _PREDICATE_KEYS
    if unknown:
        raise ValueError(f"unknown predicate keys: {sorted(unknown)}")
    return Predicate(
        contains=list(raw.get("contains", [])),
        regex=re.compile(raw["regex"], re.IGNORECASE) if "regex" in raw else None,
        line_regex=re.compile(raw["line_regex"], re.IGNORECASE) if "line_regex" in raw else None,
        any=[parse_predicate(p) for p in raw.get("any", [])],
        not_=[parse_predicate(p) for p in raw.get("not", [])],
    )


def _parse_rule(raw: dict) -> Rule:
    unknown = set(raw) - _RULE_META_KEYS - _PREDICATE_KEYS
    if unknown:
        raise ValueError(f"unknown rule keys: {sorted(unknown)}")
    state = raw["state"]
    if state not in _VALID_STATES:
        raise ValueError(f"invalid state: {state!r}")
    predicate_raw = {k: v for k, v in raw.items() if k in _PREDICATE_KEYS}
    return Rule(
        id=raw["id"],
        state=state,
        priority=int(raw["priority"]),
        region=raw["region"],
        not_footer=bool(raw.get("not_footer", False)),
        predicate=parse_predicate(predicate_raw),
    )


def _parse_manifest(path: Path) -> Manifest:
    data = tomllib.loads(path.read_text())
    rules: list[Rule] = []
    for raw_rule in data.get("rules", []):
        try:
            rules.append(_parse_rule(raw_rule))
        except (KeyError, ValueError, re.error) as exc:
            logger.warning("Skipping rule in %s: %s", path.name, exc)
    return Manifest(id=data["id"], aliases=list(data.get("aliases", [])), rules=rules)


def load_manifests(directory: str | Path) -> list[Manifest]:
    directory = Path(directory)
    manifests: list[Manifest] = []
    for path in sorted(directory.glob("*.toml")):
        try:
            manifests.append(_parse_manifest(path))
        except Exception as exc:
            logger.warning("Skipping manifest %s: %s", path.name, exc)
    return manifests
