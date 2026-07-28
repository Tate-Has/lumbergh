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
