"""The read paths a Bill without filesystem access needs to close its own loop.

Writing a brief and spawning a worker was already possible; reading anything back was not,
which made the loop one-way. These routes are the other half.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lumbergh.bill import artifacts
from lumbergh.routers import bill


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(bill.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def bill_home(tmp_path, monkeypatch):
    """Both bindings of ``home``: ``artifacts`` imported it by name, and the pre-existing
    ``POST /brief`` reaches it through ``bill_bundle``. Same function in production."""
    monkeypatch.setattr(artifacts, "home", lambda: tmp_path)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path)
    return tmp_path


def _write(client, name="flaky-login", **overrides):
    payload = {
        "name": name,
        "body": "# Findings\n\nthe shim is dead code\n",
        "actionable": True,
        "done_when": "the retry shim is gone",
        "open_questions": ["which env does CI use?"],
        "confidence": "high",
    }
    payload.update(overrides)
    return client.post("/api/bill/report", json=payload)


def test_writing_a_report_renders_the_header_and_keeps_the_prose(client, bill_home):
    r = _write(client)

    assert r.status_code == 200, r.text
    assert r.json()["path"] == str(bill_home / "reports" / "flaky-login.md")
    fm, body = artifacts.parse((bill_home / "reports" / "flaky-login.md").read_text())
    assert fm["actionable"] is True
    assert fm["open_questions"] == ["which env does CI use?"]
    assert body == "# Findings\n\nthe shim is dead code\n"


def test_a_report_cannot_escape_the_reports_directory(client):
    r = _write(client, name="../../etc/passwd")
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "name"


def test_an_actionable_report_without_a_done_when_is_refused(client, bill_home):
    r = _write(client, done_when=None)

    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "frontmatter"
    assert "done_when" in r.json()["detail"]["error"]
    assert not (bill_home / "reports").exists(), "a refused write must leave nothing behind"


def test_a_non_actionable_report_needs_no_done_when(client):
    assert _write(client, actionable=False, done_when=None).status_code == 200


def test_an_unknown_confidence_is_refused(client):
    r = _write(client, confidence="certain")
    assert r.status_code == 400
    assert "confidence" in r.json()["detail"]["error"]


def test_a_body_that_already_has_a_block_is_refused_rather_than_double_wrapped(client):
    """A scout that wrote its own frontmatter and then filed through the CLI would
    otherwise produce a file whose second block parses as prose."""
    r = _write(client, body="---\nactionable: true\n---\n\nprose\n")
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "body"


def test_reading_a_report_splits_the_header_from_the_prose(client):
    _write(client)

    d = client.get("/api/bill/report", params={"name": "flaky-login"}).json()

    assert d["exists"] is True
    assert d["frontmatter"]["confidence"] == "high"
    assert d["body"] == "# Findings\n\nthe shim is dead code\n"


def test_reading_a_report_that_is_not_there_is_a_normal_answer(client):
    d = client.get("/api/bill/report", params={"name": "nope"}).json()
    assert d["exists"] is False


def test_listing_reports_carries_the_headers(client):
    _write(client, name="a")
    _write(client, name="b", actionable=False, done_when=None, confidence="low")

    rows = client.get("/api/bill/reports").json()["reports"]

    assert [r["name"] for r in rows] == ["a", "b"]
    assert [r["actionable"] for r in rows] == [True, False]
    assert rows[0]["open_questions"] == ["which env does CI use?"]


def test_a_brief_can_be_read_back_after_it_is_written(client):
    client.post("/api/bill/brief", json={"name": "flaky-login", "body": "# Task\n\nfind it\n"})

    d = client.get("/api/bill/brief", params={"name": "flaky-login"}).json()

    assert d["exists"] is True
    assert d["body"] == "# Task\n\nfind it\n"


def test_listing_briefs_names_them(client):
    client.post("/api/bill/brief", json={"name": "b", "body": "x"})
    client.post("/api/bill/brief", json={"name": "a", "body": "x"})

    assert [b["name"] for b in client.get("/api/bill/briefs").json()["briefs"]] == ["a", "b"]


def test_listing_a_home_that_was_never_materialized_is_empty(client):
    assert client.get("/api/bill/reports").json()["reports"] == []


def test_the_scout_contract_names_the_command_and_the_delivered_line(tmp_path):
    """The path drops out of the contract entirely: a Bill on another host cannot open one,
    and a free-prose `DELIVERED:` line is not something a machine can follow."""
    text = bill._brief_delivery(tmp_path / "briefs" / "w.md", "scout", "w")

    assert "lb report write --name w" in text
    assert "DELIVERED: report w" in text
    assert "--open-question" in text
