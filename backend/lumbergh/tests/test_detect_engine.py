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
