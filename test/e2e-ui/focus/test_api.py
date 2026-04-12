"""httpx TestClient unit tests for the Focus Workspace API endpoints in Lumbergh.

Tests all /api/focus/* endpoints (tasks, archive, notes), ETag middleware,
and CORS headers. Each test gets an isolated tmp_path data directory via
the client fixture.

Run with: uv run pytest test/e2e-ui/focus/test_api.py -v
(Requires fastapi, httpx, tinydb — auto-skips when deps are missing)
"""

import pytest
from pathlib import Path

try:
    import lumbergh.db_utils  # noqa: F401
    from fastapi.testclient import TestClient
    HAS_BACKEND_DEPS = True
except ModuleNotFoundError:
    HAS_BACKEND_DEPS = False

pytestmark = pytest.mark.skipif(
    not HAS_BACKEND_DEPS,
    reason="FastAPI/TinyDB dependencies not installed (use uv run pytest)"
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a TestClient with isolated data directory."""
    import lumbergh.db_utils
    monkeypatch.setattr(lumbergh.db_utils, "FOCUS_DIR", tmp_path)

    from lumbergh.main import app
    return TestClient(app)


# -- Helpers ------------------------------------------------------------------

SAMPLE_TASK = {
    "id": "t1",
    "title": "Test",
    "project": "",
    "priority": "med",
    "status": "inbox",
    "completed": False,
    "completed_date": "",
    "blocker": "",
    "check_in_note": "",
    "session_name": "",
    "session_status": "",
    "subtasks": [],
}

SAMPLE_ARCHIVE_TASK = {
    "title": "Done",
    "project": "WW",
    "priority": "med",
    "blocker": "",
    "check_in_note": "",
    "archived_date": "2026-04-10",
}


# -- Tasks --------------------------------------------------------------------

class TestTasksAPI:
    def test_get_empty(self, client):
        r = client.get("/api/focus/tasks")
        assert r.status_code == 200
        assert r.json() == {"tasks": []}

    def test_post_and_get(self, client):
        payload = {"tasks": [SAMPLE_TASK]}
        r = client.post("/api/focus/tasks", json=payload)
        assert r.status_code == 200
        assert r.text == "ok"

        r = client.get("/api/focus/tasks")
        assert r.status_code == 200
        data = r.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["id"] == "t1"
        assert data["tasks"][0]["title"] == "Test"

    def test_export(self, client):
        # Seed a task first so the export has content
        client.post("/api/focus/tasks", json={"tasks": [SAMPLE_TASK]})

        r = client.get("/api/focus/tasks/export")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]
        assert "Test" in r.text
        # Export produces markdown with section headers
        assert "# Tasks" in r.text


# -- Archive ------------------------------------------------------------------

class TestArchiveAPI:
    def test_get_empty(self, client):
        r = client.get("/api/focus/archive")
        assert r.status_code == 200
        assert r.json() == {"tasks": [], "notes": []}

    def test_post_and_get(self, client):
        payload = {"tasks": [SAMPLE_ARCHIVE_TASK], "notes": []}
        r = client.post("/api/focus/archive", json=payload)
        assert r.status_code == 200
        assert r.text == "ok"

        r = client.get("/api/focus/archive")
        assert r.status_code == 200
        data = r.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Done"
        assert data["tasks"][0]["project"] == "WW"
        assert data["tasks"][0]["archived_date"] == "2026-04-10"

    def test_export(self, client):
        payload = {"tasks": [SAMPLE_ARCHIVE_TASK], "notes": []}
        client.post("/api/focus/archive", json=payload)

        r = client.get("/api/focus/archive/export")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]
        # Archive export includes the task title and date
        assert "Done" in r.text
        assert "2026-04-10" in r.text


# -- Notes --------------------------------------------------------------------

class TestNotesAPI:
    def test_get_empty(self, client):
        r = client.get("/api/focus/notes")
        assert r.status_code == 200
        assert r.json() == {"content": ""}

    def test_post_and_get(self, client):
        r = client.post("/api/focus/notes", json={"content": "hello world"})
        assert r.status_code == 200
        assert r.text == "ok"

        r = client.get("/api/focus/notes")
        assert r.status_code == 200
        assert r.json() == {"content": "hello world"}

    def test_export(self, client):
        client.post("/api/focus/notes", json={"content": "hello world"})

        r = client.get("/api/focus/notes/export")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]
        assert "hello world" in r.text


# -- ETag middleware ----------------------------------------------------------

class TestETag:
    def test_etag_present(self, client):
        r = client.get("/api/focus/tasks")
        assert r.status_code == 200
        assert "etag" in r.headers

    def test_304_on_match(self, client):
        r = client.get("/api/focus/tasks")
        etag = r.headers["etag"]

        r2 = client.get("/api/focus/tasks", headers={"If-None-Match": etag})
        assert r2.status_code == 304
        # 304 responses should have no body (or empty body)
        assert r2.content == b""

    def test_200_on_mismatch(self, client):
        r = client.get("/api/focus/tasks")
        assert r.status_code == 200

        r2 = client.get("/api/focus/tasks", headers={"If-None-Match": '"bogus"'})
        assert r2.status_code == 200
        assert r2.json() == {"tasks": []}

    def test_post_no_etag(self, client):
        r = client.post("/api/focus/tasks", json={"tasks": []})
        assert r.status_code == 200
        assert "etag" not in r.headers


# -- CORS ---------------------------------------------------------------------

class TestCORS:
    def test_cors_headers(self, client):
        origin = "http://localhost:3000"
        r = client.options(
            "/api/focus/tasks",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in r.headers
        # With allow_credentials=True, Starlette reflects the request
        # origin instead of returning the literal "*".
        assert r.headers["access-control-allow-origin"] == origin
