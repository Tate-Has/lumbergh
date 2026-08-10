"""The frontmatter shape a report carries, and the reads over Bill's briefs/ and reports/.

The shape exists so a Bill that cannot open the file can still act on what a scout found.
Everything here is about that: a round-trip that survives the awkward strings a real
`done_when` contains, and a parse that never punishes a report written by hand.
"""

import pytest

from lumbergh.bill import artifacts


def _round_trip(**fields):
    fm, _body = artifacts.parse(artifacts.render_frontmatter(**fields) + "\nprose\n")
    return fm


def test_render_and_parse_round_trip():
    fm = _round_trip(
        actionable=True,
        done_when="retry shim removed, suite green 10x",
        open_questions=["which env does CI use?"],
        confidence="high",
    )
    assert fm == {
        "actionable": True,
        "done_when": "retry shim removed, suite green 10x",
        "open_questions": ["which env does CI use?"],
        "confidence": "high",
    }


def test_a_done_when_containing_a_colon_survives_the_round_trip():
    """`done_when` is prose written by a model, and prose has colons in it. An unquoted
    scalar would parse back as a truncated string or as a nested key."""
    text = "config: the retry block is gone from settings.py"
    assert (
        _round_trip(actionable=True, done_when=text, open_questions=[], confidence="low")[
            "done_when"
        ]
        == text
    )


def test_open_questions_round_trip_with_awkward_characters():
    questions = ["which env does CI use?", "is `-x` still passed: yes or no?"]
    assert (
        _round_trip(
            actionable=False, done_when=None, open_questions=questions, confidence="medium"
        )["open_questions"]
        == questions
    )


def test_a_report_with_no_done_when_omits_the_key_rather_than_emitting_null():
    fm = _round_trip(actionable=False, done_when=None, open_questions=[], confidence="high")
    assert "done_when" not in fm
    assert fm["open_questions"] == []


def test_parse_returns_the_whole_text_as_body_when_there_is_no_frontmatter():
    """A report written by hand, or by a scout that predates this, still reads. It just
    reports nothing structured — losing its prose would be far worse than losing its
    fields."""
    fm, body = artifacts.parse("# Findings\n\nthe shim is dead code\n")
    assert fm == {}
    assert body == "# Findings\n\nthe shim is dead code\n"


def test_parse_ignores_keys_it_does_not_know():
    fm, body = artifacts.parse("---\nactionable: true\nauthor: someone\n---\n\nprose\n")
    assert fm == {"actionable": True}
    assert body == "prose\n"


def test_parse_leaves_a_lone_opening_marker_as_body():
    """A body that happens to start with a horizontal rule is not a truncated frontmatter
    block, and swallowing it would silently eat the report."""
    text = "---\n\n# Findings\n"
    fm, body = artifacts.parse(text)
    assert fm == {}
    assert body == text


@pytest.mark.parametrize(
    ("actionable", "done_when", "confidence", "expected"),
    [
        (True, "the shim is gone", "high", None),
        (False, None, "low", None),
        (True, None, "high", "done_when"),
        (True, "   ", "high", "done_when"),
        (True, "the shim is gone", "certain", "confidence"),
        (True, "the shim is gone", None, "confidence"),
    ],
)
def test_validate_enforces_the_conditional_rules(actionable, done_when, confidence, expected):
    """`done_when` is required only for an actionable report: a "nothing to do here"
    report has no done-when, and a required field that must be invented is one that lies."""
    error = artifacts.validate(actionable, done_when, confidence)
    if expected is None:
        assert error is None
    else:
        assert error is not None
        assert expected in error


def test_write_report_puts_the_frontmatter_above_the_prose(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "home", lambda: tmp_path)

    path = artifacts.write_report(
        "flaky-login",
        "# Findings\n\nthe shim is dead code\n",
        actionable=True,
        done_when="shim removed",
        open_questions=["which env does CI use?"],
        confidence="high",
    )

    assert path == tmp_path / "reports" / "flaky-login.md"
    fm, body = artifacts.parse(path.read_text())
    assert fm["actionable"] is True
    assert body == "# Findings\n\nthe shim is dead code\n"


def test_listing_reports_carries_the_frontmatter_so_a_reader_can_triage_without_fetching(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(artifacts, "home", lambda: tmp_path)
    artifacts.write_report(
        "b", "prose", actionable=False, done_when=None, open_questions=[], confidence="low"
    )
    artifacts.write_report(
        "a", "prose", actionable=True, done_when="done", open_questions=["q?"], confidence="high"
    )

    rows = artifacts.listing("reports")

    assert [r["name"] for r in rows] == ["a", "b"], "listings sort by name, not by mtime"
    assert rows[0]["actionable"] is True
    assert rows[0]["confidence"] == "high"
    assert rows[0]["open_questions"] == ["q?"]
    assert rows[0]["bytes"] > 0
    assert rows[0]["modified"]


def test_listing_a_directory_that_was_never_materialized_is_empty_not_an_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(artifacts, "home", lambda: tmp_path / "nothing")
    assert artifacts.listing("briefs") == []


def test_read_artifact_reports_a_missing_one_rather_than_raising(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "home", lambda: tmp_path)
    assert artifacts.read_artifact("reports", "nope")["exists"] is False


def test_read_artifact_on_a_brief_returns_its_body_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "home", lambda: tmp_path)
    (tmp_path / "briefs").mkdir()
    (tmp_path / "briefs" / "flaky-login.md").write_text("# Task\n\nfind the flake\n")

    d = artifacts.read_artifact("briefs", "flaky-login")

    assert d["exists"] is True
    assert d["body"] == "# Task\n\nfind the flake\n"
    assert "frontmatter" not in d, "a brief has no contracted shape — only a report does"
