# Manifest-Driven Detection Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded regexes in `idle_detector.py` with a data-driven engine that reads Lumbergh-native TOML manifests, while preserving current detection behavior exactly.

**Architecture:** An override-only engine (`detect/`) returns `"blocked"`/`"error"`/`None` from priority-ordered manifest rules. `idle_detector.classify_overrides` becomes a thin shim that delegates to the engine and maps its string result to `SessionState`. The burst-fingerprint quiescence classifier in `idle_monitor` still owns `WORKING`/`IDLE`. A new `capture_pane_title` feeds the `osc_title` region once per poll.

**Tech Stack:** Python 3.11+ (`tomllib` stdlib, no new deps), pytest, libtmux/tmux subprocess.

## Global Constraints

- Python **3.11+** — use `tomllib` from the standard library; add no new dependencies.
- **`backend/lumbergh/tests/test_idle_detector.py` must pass completely unchanged** — it is the behavioral-parity contract. Do not edit it.
- `classify_overrides` keeps a **default second parameter** (`osc_title: str = ""`) so existing single-arg call sites and tests stay valid.
- The engine must **never raise into the monitor loop**: on any internal error, return `None` (defer to quiescence).
- All manifest `contains`/`regex`/`line_regex` matching is **case-insensitive**.
- Run `./lint.sh` clean before completion.
- Every commit message: no AI attribution / Co-Authored-By lines.

---

### Task 1: Region extraction

**Files:**
- Create: `backend/lumbergh/detect/__init__.py` (empty)
- Create: `backend/lumbergh/detect/regions.py`
- Test: `backend/lumbergh/tests/test_regions.py`

**Interfaces:**
- Produces: `extract(region: str, content: str, osc_title: str) -> list[str]`. Supported `region` values: `"recent"` (last 15 non-empty lines), `"recent_lines(N)"` (last N), `"osc_title"` (the title as a single-element list, or `[]` if empty). Unknown region → `[]`. All lines have ANSI stripped and trailing whitespace removed; trailing blank lines are dropped before slicing.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_regions.py
from lumbergh.detect.regions import extract

ANSI = "\x1b[32m● done\x1b[0m\n\x1b[1mline two\x1b[0m\n\n\n"


def test_recent_strips_ansi_and_trailing_blanks():
    assert extract("recent", ANSI, "") == ["● done", "line two"]


def test_recent_lines_takes_last_n():
    content = "a\nb\nc\nd\n"
    assert extract("recent_lines(2)", content, "") == ["c", "d"]


def test_recent_caps_at_fifteen():
    content = "\n".join(str(i) for i in range(20)) + "\n"
    assert extract("recent", content, "") == [str(i) for i in range(5, 20)]


def test_osc_title_returns_title():
    assert extract("osc_title", "ignored body", "✻ Baking") == ["✻ Baking"]


def test_osc_title_empty_returns_empty_list():
    assert extract("osc_title", "body", "") == []


def test_unknown_region_returns_empty():
    assert extract("bogus", "a\nb\n", "") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_regions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.detect'`

- [ ] **Step 3: Implement `regions.py`**

```python
# backend/lumbergh/detect/regions.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_regions.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/detect/__init__.py backend/lumbergh/detect/regions.py backend/lumbergh/tests/test_regions.py
git commit -m "feat(detect): region extraction for manifest engine"
```

---

### Task 2: Manifest data model and loader

**Files:**
- Create: `backend/lumbergh/detect/manifest.py`
- Test: `backend/lumbergh/tests/test_manifest.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `Predicate` dataclass: `contains: list[str]`, `regex: re.Pattern | None`, `line_regex: re.Pattern | None`, `any: list[Predicate]`, `not_: list[Predicate]`.
  - `Rule` dataclass: `id: str`, `state: str` (`"blocked"`/`"error"`/`"none"`), `priority: int`, `region: str`, `not_footer: bool`, `predicate: Predicate`.
  - `Manifest` dataclass: `id: str`, `aliases: list[str]`, `rules: list[Rule]`.
  - `load_manifests(directory: str | Path) -> list[Manifest]` — parses every `*.toml`; skips (with a logged warning) any rule with an unknown state, a bad regex, or an unknown predicate key, and skips any manifest file that fails to parse, without affecting siblings.
  - `parse_predicate(raw: dict) -> Predicate` (used by the loader; exposed for tests).

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_manifest.py
from pathlib import Path

from lumbergh.detect.manifest import load_manifests

VALID = """
id = "demo"
aliases = ["demo-alias"]

[[rules]]
id = "perm"
state = "blocked"
priority = 800
region = "recent"
not_footer = true
any = [ { contains = ["do you want to"] }, { contains = ["would you like to"] } ]
line_regex = "^\\\\s*\\\\d+\\\\.\\\\s*(yes|no)\\\\b"
not = [ { contains = ["select model"] } ]
"""

BAD_REGEX = """
id = "badre"
[[rules]]
id = "r1"
state = "blocked"
priority = 100
region = "recent"
regex = "("
[[rules]]
id = "r2"
state = "error"
priority = 90
region = "recent"
contains = ["overloaded"]
"""

BAD_STATE = """
id = "badstate"
[[rules]]
id = "r1"
state = "working"
priority = 100
region = "recent"
contains = ["x"]
"""

UNKNOWN_KEY = """
id = "unknownkey"
[[rules]]
id = "r1"
state = "blocked"
priority = 100
region = "recent"
sometimes = ["x"]
"""


def _write(tmp_path: Path, name: str, body: str) -> None:
    (tmp_path / name).write_text(body)


def test_loads_valid_manifest(tmp_path):
    _write(tmp_path, "demo.toml", VALID)
    manifests = load_manifests(tmp_path)
    assert len(manifests) == 1
    m = manifests[0]
    assert m.id == "demo"
    assert m.aliases == ["demo-alias"]
    assert len(m.rules) == 1
    rule = m.rules[0]
    assert rule.state == "blocked"
    assert rule.priority == 800
    assert rule.not_footer is True
    assert rule.predicate.line_regex is not None


def test_bad_regex_rule_skipped_siblings_survive(tmp_path):
    _write(tmp_path, "badre.toml", BAD_REGEX)
    manifests = load_manifests(tmp_path)
    assert len(manifests) == 1
    ids = [r.id for r in manifests[0].rules]
    assert ids == ["r2"]


def test_unknown_state_rule_skipped(tmp_path):
    _write(tmp_path, "badstate.toml", BAD_STATE)
    manifests = load_manifests(tmp_path)
    assert manifests[0].rules == []


def test_unknown_predicate_key_rule_skipped(tmp_path):
    _write(tmp_path, "unknownkey.toml", UNKNOWN_KEY)
    manifests = load_manifests(tmp_path)
    assert manifests[0].rules == []


def test_malformed_toml_skips_only_that_file(tmp_path):
    _write(tmp_path, "good.toml", VALID)
    _write(tmp_path, "broken.toml", "this is = = not toml")
    manifests = load_manifests(tmp_path)
    assert [m.id for m in manifests] == ["demo"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.detect.manifest'`

- [ ] **Step 3: Implement `manifest.py`**

```python
# backend/lumbergh/detect/manifest.py
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
        except Exception as exc:  # noqa: BLE001 - one bad file must not sink the rest
            logger.warning("Skipping manifest %s: %s", path.name, exc)
    return manifests
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_manifest.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/detect/manifest.py backend/lumbergh/tests/test_manifest.py
git commit -m "feat(detect): manifest data model and defensive loader"
```

---

### Task 3: Classification engine

**Files:**
- Create: `backend/lumbergh/detect/engine.py`
- Test: `backend/lumbergh/tests/test_detect_engine.py`

**Interfaces:**
- Consumes: `regions.extract` (Task 1); `Manifest`, `Rule`, `Predicate` (Task 2).
- Produces: `classify(content: str, osc_title: str, manifests: list[Manifest]) -> str | None`. Flattens all rules across all manifests, sorts by descending `priority`, and returns the `state` of the first rule whose predicate (and `not_footer` guard) passes — except a matched `"none"` rule returns `None` (veto short-circuit). No match → `None`. Never raises: any internal error is caught and yields `None`.

**Notes for the implementer:**
- Footer markers for `not_footer`: a rule fails if any of the last 3 cleaned lines contains (case-insensitive) `"shift+tab to cycle"`, `"esc to interrupt"`, or `"? for shortcuts"`.
- A predicate passes when ALL present clauses pass: every string in `contains` is a case-insensitive substring of the region blob; `regex` matches the blob; `line_regex` matches at least one region line; every clause in `any` — if present — has at least one true; every clause in `not` is false.
- The engine speaks manifest strings only; it must not import `idle_detector` (avoids a circular import).

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_detect_engine.py
from lumbergh.detect.engine import classify
from lumbergh.detect.manifest import load_manifests

MANIFEST = """
id = "t"

[[rules]]
id = "veto_menu"
state = "none"
priority = 900
region = "recent"
any = [ { contains = ["select model"] } ]

[[rules]]
id = "form"
state = "blocked"
priority = 700
region = "recent"
not_footer = true
contains = ["enter to select"]
any = [ { contains = ["esc to cancel"] }, { contains = ["to navigate"] } ]

[[rules]]
id = "err"
state = "error"
priority = 1000
region = "recent"
any = [ { regex = "overloaded" } ]

[[rules]]
id = "title_block"
state = "blocked"
priority = 500
region = "osc_title"
regex = "waiting"
"""


def _manifests(tmp_path):
    (tmp_path / "t.toml").write_text(MANIFEST)
    return load_manifests(tmp_path)


def test_blocked_form_matches(tmp_path):
    content = "Choose an option:\nenter to select\nesc to cancel\n"
    assert classify(content, "", _manifests(tmp_path)) == "blocked"


def test_error_beats_blocked_by_priority(tmp_path):
    content = "overloaded\nenter to select\nesc to cancel\n"
    assert classify(content, "", _manifests(tmp_path)) == "error"


def test_veto_short_circuits_lower_blocked(tmp_path):
    content = "Select model\nenter to select\nesc to cancel\n"
    assert classify(content, "", _manifests(tmp_path)) is None


def test_not_footer_vetoes_when_live_footer_present(tmp_path):
    content = "enter to select\nesc to cancel\n? for shortcuts\n"
    assert classify(content, "", _manifests(tmp_path)) is None


def test_osc_title_drives_blocked(tmp_path):
    assert classify("idle body\n", "waiting for auth", _manifests(tmp_path)) == "blocked"


def test_no_match_returns_none(tmp_path):
    assert classify("just some normal output\n", "", _manifests(tmp_path)) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_detect_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.detect.engine'`

- [ ] **Step 3: Implement `engine.py`**

```python
# backend/lumbergh/detect/engine.py
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
    if any(_predicate_passes(clause, blob_lower, lines) for clause in predicate.not_):
        return False
    return True


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
    except Exception as exc:  # noqa: BLE001 - detection must never break the monitor loop
        logger.warning("Detection engine error, deferring to quiescence: %s", exc)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_detect_engine.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/detect/engine.py backend/lumbergh/tests/test_detect_engine.py
git commit -m "feat(detect): priority-ordered classification engine"
```

---

### Task 4: Bundled manifests

**Files:**
- Create: `backend/lumbergh/detect/manifests/common.toml`
- Create: `backend/lumbergh/detect/manifests/claude.toml`
- Create: `backend/lumbergh/detect/manifests/pi.toml`
- Create: `backend/lumbergh/detect/manifests/README.md`
- Test: `backend/lumbergh/tests/test_bundled_manifests.py`

**Interfaces:**
- Consumes: `load_manifests` (Task 2).
- Produces: the bundled manifest directory used by the Task 5 shim via `manifests_dir()` (added in Task 5). This task only guarantees the files parse with no dropped rules.

**Notes:** These rules were derived by hand-tracing the 10 cases in `test_idle_detector.py`; Task 5 is where the parity suite proves them. The `❯` glyph is U+276F — paste it literally.

- [ ] **Step 1: Write `common.toml`**

```toml
# Agent-agnostic overrides: API/connection errors and a bare shell prompt
# (the agent exited and the user is back at their shell).
id = "common"

[[rules]]
id = "api_error"
state = "error"
priority = 1000
region = "recent"
any = [
  { regex = "rate limit|rate_limit" },
  { regex = "\\b429\\b|too many requests" },
  { regex = "overloaded" },
  { regex = "APIError|API error|APIConnectionError" },
  { regex = "unexpected error|Connection error" },
]

[[rules]]
id = "shell_prompt"
state = "error"
priority = 200
region = "recent"
regex = "[$%#]\\s*\\Z"
not = [
  { contains = ["esc to interrupt"] },
  { contains = ["esc to cancel"] },
  { contains = ["shift+tab to cycle"] },
  { contains = ["accept edits"] },
  { contains = ["? for shortcuts"] },
]
```

- [ ] **Step 2: Write `claude.toml`**

```toml
# Claude Code TUI family. The engine applies every manifest to every pane, so
# these also cover Pi (which shares the same prompt UI); pi.toml adds only
# pi-branded phrasing.
id = "claude"
aliases = ["claude-code"]

# Veto: transient menus the *user* opened (model/theme picker, transcript view)
# look like selectable forms but are not the agent blocking on a decision.
[[rules]]
id = "transient_menu"
state = "none"
priority = 900
region = "recent"
any = [
  { contains = ["select model"] },
  { contains = ["set as default"] },
  { contains = ["select theme"] },
  { contains = ["output style"] },
  { contains = ["showing detailed transcript"] },
]

# Permission / plan approval: a "do you want to…/would you like to…" question
# together with a numbered Yes/No option block.
[[rules]]
id = "permission_dialog"
state = "blocked"
priority = 800
region = "recent"
not_footer = true
any = [
  { contains = ["do you want to"] },
  { contains = ["would you like to"] },
]
line_regex = "^\\s*❯?\\s*\\d+\\.\\s*(yes|no)\\b"

# Interactive login / auth prompts.
[[rules]]
id = "interactive_login"
state = "blocked"
priority = 750
region = "recent"
not_footer = true
any = [
  { contains = ["do you want to allow this connection?"] },
  { contains = ["paste the code"] },
  { contains = ["paste your authorization code"] },
  { contains = ["enter your authorization code"] },
  { contains = ["waiting for authentication"] },
]

# Selectable form: "enter to select" plus a navigation hint.
[[rules]]
id = "selectable_form"
state = "blocked"
priority = 700
region = "recent"
not_footer = true
contains = ["enter to select"]
any = [
  { contains = ["to navigate"] },
  { contains = ["esc to cancel"] },
]
```

- [ ] **Step 3: Write `pi.toml`**

```toml
# Pi-specific phrasing. Its trust prompt is already caught by claude.toml's
# permission_dialog; this rule adds the pi-branded signal explicitly.
id = "pi"
aliases = ["herdr:pi"]

[[rules]]
id = "pi_trust_prompt"
state = "blocked"
priority = 800
region = "recent"
not_footer = true
contains = ["wants to run"]
line_regex = "^\\s*❯?\\s*\\d+\\.\\s*(yes|no)\\b"
```

- [ ] **Step 4: Write `README.md`**

```markdown
# Detection manifests

Priority-ordered rules that classify a captured pane as `blocked`/`error`
(an override) or veto detection (`none`, defer to the quiescence classifier).
See `docs/superpowers/specs/2026-07-27-manifest-detection-engine-design.md`.

Rule *content* (the observable strings agents print) was adapted from
[ogulcancelik/herdr](https://github.com/ogulcancelik/herdr) at commit `dc2506e`
(Apache-2.0), reworked into Lumbergh's own manifest schema. These are factual
observations of third-party agent UIs, not a copy of herdr's files.
```

- [ ] **Step 5: Write the parse-integrity test**

```python
# backend/lumbergh/tests/test_bundled_manifests.py
from pathlib import Path

from lumbergh.detect.manifest import load_manifests

MANIFESTS_DIR = Path(__file__).resolve().parents[1] / "detect" / "manifests"


def test_all_bundled_manifests_parse_with_no_dropped_rules():
    manifests = load_manifests(MANIFESTS_DIR)
    ids = {m.id for m in manifests}
    assert {"common", "claude", "pi"} <= ids
    for manifest in manifests:
        assert manifest.rules, f"{manifest.id} has no rules (all dropped as invalid?)"
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_bundled_manifests.py -v`
Expected: PASS (1 passed). If a manifest reports zero rules, a rule was dropped — check the warning log for the offending regex/state.

- [ ] **Step 7: Commit**

```bash
git add backend/lumbergh/detect/manifests/ backend/lumbergh/tests/test_bundled_manifests.py
git commit -m "feat(detect): bundled common/claude/pi manifests"
```

---

### Task 5: Shim `idle_detector` onto the engine (parity gate)

**Files:**
- Modify: `backend/lumbergh/idle_detector.py` (replace the pattern/`classify_*` internals; keep the `SessionState` enum and the `classify_overrides` public name)
- Test: `backend/lumbergh/tests/test_idle_detector.py` (existing — **must pass unchanged, do not edit**)

**Interfaces:**
- Consumes: `engine.classify` (Task 3); `load_manifests` (Task 2); the bundled directory (Task 4).
- Produces:
  - `SessionState` (unchanged enum — other modules import it from here).
  - `classify_overrides(content: str, osc_title: str = "") -> SessionState | None`.
  - `manifests_dir() -> Path` — absolute path to `detect/manifests`.

- [ ] **Step 1: Run the existing parity suite against the current code (baseline)**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_detector.py -v`
Expected: PASS (10 passed) — this is the behavior to preserve.

- [ ] **Step 2: Replace `idle_detector.py` internals with the shim**

Preserve the `SessionState` enum exactly. Replace everything below it (all the
`_*` patterns, `_strip_ansi`, `_recent_lines`, `classify_blocked`, and the body
of `classify_overrides`) with:

```python
from functools import lru_cache
from pathlib import Path

from lumbergh.detect.engine import classify as _engine_classify
from lumbergh.detect.manifest import load_manifests

_STATE_MAP = {"blocked": SessionState.BLOCKED, "error": SessionState.ERROR}


def manifests_dir() -> Path:
    return Path(__file__).resolve().parent / "detect" / "manifests"


@lru_cache(maxsize=1)
def _manifests():
    return load_manifests(manifests_dir())


def classify_overrides(content: str, osc_title: str = "") -> SessionState | None:
    """Return a BLOCKED/ERROR override, or None to defer to quiescence.

    Delegates to the manifest engine; the string result is mapped to the app's
    SessionState. A veto rule and a no-match both yield None.
    """
    state = _engine_classify(content, osc_title, _manifests())
    return _STATE_MAP.get(state) if state else None
```

Also update the module docstring to say detection is now manifest-driven
(`detect/manifests/*.toml`) with quiescence still owning WORKING/IDLE.

- [ ] **Step 3: Run the parity suite — the acceptance gate**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_detector.py -v`
Expected: PASS (10 passed), with the test file unmodified.
If any case fails, fix the manifest rules in Task 4 (not the test): compare the
failing snapshot against the rule that should match it and adjust
region/predicate/priority until parity holds.

- [ ] **Step 4: Run the whole detect + detector suite together**

Run: `cd backend && uv run pytest lumbergh/tests/test_regions.py lumbergh/tests/test_manifest.py lumbergh/tests/test_detect_engine.py lumbergh/tests/test_bundled_manifests.py lumbergh/tests/test_idle_detector.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/idle_detector.py
git commit -m "refactor(detect): drive classify_overrides from manifest engine"
```

---

### Task 6: Capture the pane title

**Files:**
- Modify: `backend/lumbergh/tmux_pty.py` (add `capture_pane_title` near `capture_pane_content`)
- Test: `backend/lumbergh/tests/test_capture_pane_title.py`

**Interfaces:**
- Produces: `capture_pane_title(session_name: str) -> str` — the pane's title via `tmux display-message -p '#{pane_title}'`, stripped; `""` on non-zero exit, timeout, or any exception.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_capture_pane_title.py
import subprocess
from unittest.mock import patch

from lumbergh.tmux_pty import capture_pane_title


def _completed(stdout="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


def test_returns_stripped_title():
    with patch("lumbergh.tmux_pty.subprocess.run", return_value=_completed("✻ Baking\n")):
        assert capture_pane_title("sess") == "✻ Baking"


def test_nonzero_exit_returns_empty():
    with patch("lumbergh.tmux_pty.subprocess.run", return_value=_completed("x", returncode=1)):
        assert capture_pane_title("sess") == ""


def test_exception_returns_empty():
    with patch("lumbergh.tmux_pty.subprocess.run", side_effect=OSError("boom")):
        assert capture_pane_title("sess") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_capture_pane_title.py -v`
Expected: FAIL — `ImportError: cannot import name 'capture_pane_title'`

- [ ] **Step 3: Implement `capture_pane_title`**

Add to `backend/lumbergh/tmux_pty.py` (immediately after `capture_pane_content`):

```python
def capture_pane_title(session_name: str) -> str:
    """Return the active pane's OSC-set title (``#{pane_title}``), or "".

    A single lightweight ``display-message`` call. Failures degrade to an empty
    string, in which case ``osc_title`` detection rules simply do not match.
    """
    try:
        result = subprocess.run(
            [TMUX_CMD, "display-message", "-t", session_name, "-p", "#{pane_title}"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_capture_pane_title.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/tmux_pty.py backend/lumbergh/tests/test_capture_pane_title.py
git commit -m "feat(tmux): capture pane title for osc_title detection"
```

---

### Task 7: Wire the title through the monitor

**Files:**
- Modify: `backend/lumbergh/idle_monitor.py` (`_check_session` fetches the title once per poll; `_classify_burst` accepts and forwards `osc_title`)
- Test: `backend/lumbergh/tests/test_idle_monitor_title.py`

**Interfaces:**
- Consumes: `capture_pane_title` (Task 6); `classify_overrides(content, osc_title)` (Task 5).
- Produces: `_classify_burst(self, session_name, captures, now, osc_title="")` — the `osc_title` is passed straight to `classify_overrides`.

**Notes:** The import line is `from lumbergh.tmux_pty import IS_WINDOWS, capture_pane_content` (`idle_monitor.py:35`). Add `capture_pane_title` to it. The title is fetched once per `_check_session`, not per burst frame, and only for its use in `classify_overrides`.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_idle_monitor_title.py
from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import IdleMonitor


def test_classify_burst_forwards_osc_title(monkeypatch):
    captured = {}

    def fake_classify(content, osc_title=""):
        captured["osc_title"] = osc_title
        return None

    monkeypatch.setattr("lumbergh.idle_monitor.classify_overrides", fake_classify)
    monitor = IdleMonitor()
    monitor._classify_burst("sess", ["stable frame"], now=1000.0, osc_title="✻ waiting")
    assert captured["osc_title"] == "✻ waiting"


def test_classify_burst_default_title_is_empty(monkeypatch):
    captured = {}

    def fake_classify(content, osc_title=""):
        captured["osc_title"] = osc_title
        return SessionState.BLOCKED

    monkeypatch.setattr("lumbergh.idle_monitor.classify_overrides", fake_classify)
    monitor = IdleMonitor()
    result = monitor._classify_burst("sess", ["frame"], now=1000.0)
    assert result == SessionState.BLOCKED
    assert captured["osc_title"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_title.py -v`
Expected: FAIL — `TypeError: _classify_burst() got an unexpected keyword argument 'osc_title'`

- [ ] **Step 3: Update the import**

At `backend/lumbergh/idle_monitor.py:35`, change:

```python
from lumbergh.tmux_pty import IS_WINDOWS, capture_pane_content
```

to:

```python
from lumbergh.tmux_pty import IS_WINDOWS, capture_pane_content, capture_pane_title
```

- [ ] **Step 4: Add `osc_title` to `_classify_burst`**

Change the signature (currently `def _classify_burst(self, session_name, captures, now):`) and the `classify_overrides` call inside it:

```python
    def _classify_burst(
        self, session_name: str, captures: list[str], now: float, osc_title: str = ""
    ) -> SessionState:
        if not captures:
            return SessionState.UNKNOWN

        override = classify_overrides(captures[-1], osc_title)
        if override is not None:
            return override
```

(Leave the rest of the method unchanged.)

- [ ] **Step 5: Fetch the title in `_check_session` and pass it through**

In `_check_session`, after the `if not any(captures): return` guard, fetch the
title once and forward it:

```python
        loop = asyncio.get_event_loop()
        osc_title = await loop.run_in_executor(None, capture_pane_title, session_name)

        state = self._classify_burst(session_name, captures, time.time(), osc_title)
```

(Replace the existing `state = self._classify_burst(session_name, captures, time.time())` line.)

- [ ] **Step 6: Run the new tests and the parity suite**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_title.py lumbergh/tests/test_idle_detector.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/lumbergh/idle_monitor.py backend/lumbergh/tests/test_idle_monitor_title.py
git commit -m "feat(monitor): feed pane title to detection once per poll"
```

---

### Task 8: Packaging, top-level provenance, and full verification

**Files:**
- Modify: `backend/pyproject.toml` (ensure the `*.toml` manifests ship in the wheel)
- Modify: `README.md` (top-level provenance line)

**Interfaces:** none.

- [ ] **Step 1: Confirm manifests are packaged**

Inspect `backend/pyproject.toml` for its build config. If it uses setuptools
package discovery without data-file inclusion, add the manifests as package
data so they exist at runtime in an installed wheel. For a setuptools build,
add:

```toml
[tool.setuptools.package-data]
"lumbergh" = ["detect/manifests/*.toml", "detect/manifests/*.md"]
```

If the project uses hatchling or another backend, add the equivalent
`force-include`/`artifacts` entry. Verify with:

Run: `cd backend && uv build 2>/dev/null && python -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); print([n for n in z.namelist() if 'manifests' in n])"`
Expected: the list includes `lumbergh/detect/manifests/common.toml`, `claude.toml`, `pi.toml`.

- [ ] **Step 2: Add the top-level provenance line**

Add to `README.md` (in an existing "Credits"/"Acknowledgements" section, or a
new one near the license note):

```markdown
## Acknowledgements

Agent-detection manifest *content* (`backend/lumbergh/detect/manifests/`) was
adapted from [herdr](https://github.com/ogulcancelik/herdr) (Apache-2.0),
reworked into Lumbergh's own manifest schema.
```

- [ ] **Step 3: Run the full backend test suite**

Run: `cd backend && uv run pytest`
Expected: all PASS (all prior suites plus the rest of the backend).

- [ ] **Step 4: Lint**

Run: `./lint.sh`
Expected: exits 0 (auto-fixes applied; no remaining errors). If it reports unfixable errors, fix them and re-run.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml README.md
git commit -m "chore(detect): package manifests and credit herdr provenance"
```

---

## Self-Review

**Spec coverage:**
- Override-only engine returning blocked/error/None → Tasks 3, 5. ✓
- Bundled manifests, lean TOML format (regions, predicate algebra, states, `not_footer`) → Tasks 1–4. ✓
- `common.toml` for error/shell, `claude.toml`/`pi.toml` for blocked → Task 4. ✓
- OSC/pane-title captured once per poll, defined region → Tasks 1, 6, 7. ✓
- `classify_overrides` gains `osc_title=""`, existing test unchanged → Task 5, Global Constraints. ✓
- Defensive loading (skip bad rule/manifest), engine never raises → Tasks 2, 3. ✓
- Regression parity via unchanged `test_idle_detector.py` → Task 5 (the gate). ✓
- Licensing: manifests README provenance + top-level README → Tasks 4, 8. ✓
- No new dependency (`tomllib` stdlib) → Global Constraints. ✓
- Follow-up bites (remote catalog, positive working/idle) explicitly deferred — not in any task. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command has expected output. ✓

**Type consistency:** `classify(content, osc_title, manifests) -> str | None` (Task 3) is called by the shim (Task 5) and mapped via `_STATE_MAP`. `extract(region, content, osc_title) -> list[str]` (Task 1) used by engine (Task 3). `capture_pane_title(session_name) -> str` (Task 6) used in monitor (Task 7). `_classify_burst(..., osc_title="")` (Task 7) forwards to `classify_overrides(content, osc_title)` (Task 5). Names and signatures match across tasks. ✓
