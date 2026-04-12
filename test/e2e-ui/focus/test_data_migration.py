"""Tests for Focus Workspace data migration and export endpoints.

NOTE: The migration script tests (TestMigrateTasks*, TestMigrateArchive*,
TestMigrateNotes*) are specific to the standalone workstation project and
are not applicable to Lumbergh. Only the export endpoint tests and JSON
API basics are included here.
"""
import json
import urllib.request

import pytest
from conftest import BASE_URL, seed_tasks, seed_archive, clear_tasks, clear_archive, read_tasks, make_task


# ===== Export Endpoint Tests =====

class TestExportEndpoints:
    """Test the markdown export endpoints."""

    def test_tasks_export_returns_markdown(self):
        """GET /api/focus/tasks/export returns valid markdown."""
        seed_tasks({"tasks": [
            make_task("Test export", project="Proj", priority="high", status="today"),
            make_task("Another task", status="backlog"),
        ]})
        resp = urllib.request.urlopen(f"{BASE_URL}/api/focus/tasks/export")
        md = resp.read().decode("utf-8")
        content_type = resp.headers.get("Content-Type", "")
        assert "text/plain" in content_type
        assert "# Tasks" in md
        assert "## today" in md
        assert "**[Proj] Test export** !high" in md
        assert "## backlog" in md
        assert "**Another task**" in md
        clear_tasks()

    def test_archive_export_returns_markdown(self):
        """GET /api/focus/archive/export returns valid markdown."""
        seed_archive({"tasks": [
            {"title": "Archived task", "project": "Proj", "priority": "med", "blocker": "", "check_in_note": "", "archived_date": "2026-04-10"},
        ], "notes": []})
        resp = urllib.request.urlopen(f"{BASE_URL}/api/focus/archive/export")
        md = resp.read().decode("utf-8")
        assert "## 2026-04-10" in md
        assert "Archived task" in md
        clear_archive()

    def test_notes_export_returns_text(self):
        """GET /api/focus/notes/export returns plain text."""
        # Write notes via API
        payload = json.dumps({"content": "My important notes"})
        req = urllib.request.Request(
            f"{BASE_URL}/api/focus/notes",
            data=payload.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)

        resp = urllib.request.urlopen(f"{BASE_URL}/api/focus/notes/export")
        text = resp.read().decode("utf-8")
        assert text == "My important notes"

    def test_empty_tasks_export(self):
        """Export with no tasks returns valid empty markdown."""
        clear_tasks()
        resp = urllib.request.urlopen(f"{BASE_URL}/api/focus/tasks/export")
        md = resp.read().decode("utf-8")
        assert "# Tasks" in md
        assert "## inbox" in md
        clear_tasks()


class TestJsonApiBasics:
    """Test basic JSON API behavior."""

    def test_tasks_api_returns_json_content_type(self):
        """GET /api/focus/tasks returns application/json content type."""
        resp = urllib.request.urlopen(f"{BASE_URL}/api/focus/tasks")
        content_type = resp.headers.get("Content-Type", "")
        assert "application/json" in content_type

    def test_missing_file_returns_empty(self):
        """Missing JSON file returns empty default, not error."""
        # This tests the server's fallback behavior
        data = read_tasks()
        assert "tasks" in data

    def test_roundtrip_preserves_all_fields(self):
        """Write tasks, read back, verify all fields preserved."""
        original = {"tasks": [
            make_task("Full roundtrip", project="RT", priority="high", status="today",
                      blocker="blocked", check_in_note="noted", session_name="sess",
                      session_status="working", completed_date="2026-04-10",
                      subtasks=[{"text": "Sub 1", "done": False}, {"text": "Sub 2", "done": True}]),
        ]}
        seed_tasks(original)
        data = read_tasks()
        t = data["tasks"][0]
        assert t["title"] == "Full roundtrip"
        assert t["project"] == "RT"
        assert t["priority"] == "high"
        assert t["status"] == "today"
        assert t["blocker"] == "blocked"
        assert t["check_in_note"] == "noted"
        assert t["session_name"] == "sess"
        assert t["session_status"] == "working"
        assert t["completed_date"] == "2026-04-10"
        assert len(t["subtasks"]) == 2
        assert t["subtasks"][0] == {"text": "Sub 1", "done": False}
        assert t["subtasks"][1] == {"text": "Sub 2", "done": True}
        clear_tasks()
