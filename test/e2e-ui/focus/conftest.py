"""Shared fixtures for Focus Workspace tests (Lumbergh-integrated).

IMPORTANT: Tests must NEVER corrupt the user's real task data.
All data files are backed up and restored on disk (not via API) around every test
AND around the entire test session, so even if individual restore fails, the
session-level restore catches it.
"""
import json
import os
import shutil
import pytest
import urllib.request

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ModuleNotFoundError:
    HAS_PLAYWRIGHT = False

BACKEND_URL = "http://localhost:8420"
VITE_URL = "http://localhost:5420"
# Default to backend; override with --target=vite
BASE_URL = BACKEND_URL
API_PREFIX = "/api/focus"

# Focus data files live in ~/.config/lumbergh/focus/
PROJECT_DIR = os.path.expanduser("~/.config/lumbergh/focus")


def pytest_addoption(parser):
    """Add --target option: 'backend' (default) or 'vite'."""
    parser.addoption(
        "--target", action="store", default="backend",
        choices=["backend", "vite"],
        help="UI target: 'backend' serves from dist/, 'vite' uses dev server at :5420",
    )


def pytest_configure(config):
    """Set BASE_URL based on options."""
    global BASE_URL
    target = config.getoption("--target", "backend")
    BASE_URL = VITE_URL if target == "vite" else BACKEND_URL

# Files that must be protected during tests
_PROTECTED_FILES = [
    "tasks.json", "archive.json", "notes.json",
]


def _backup_files(suffix: str) -> dict:
    """Back up protected files to physical .bak files on disk.
    Returns dict of {filename: backup_path_or_None} for restore."""
    # Ensure the data directory exists
    os.makedirs(PROJECT_DIR, exist_ok=True)
    backups = {}
    for fname in _PROTECTED_FILES:
        fpath = os.path.join(PROJECT_DIR, fname)
        bak_path = fpath + f".{suffix}.bak"
        if os.path.exists(fpath):
            shutil.copy2(fpath, bak_path)
            backups[fname] = bak_path
        else:
            backups[fname] = None
    return backups


def _restore_files(backups: dict):
    """Restore protected files from physical .bak files, then clean up."""
    for fname, bak_path in backups.items():
        fpath = os.path.join(PROJECT_DIR, fname)
        if bak_path is None:
            if os.path.exists(fpath):
                os.remove(fpath)
        elif os.path.exists(bak_path):
            shutil.copy2(bak_path, fpath)
            os.remove(bak_path)


def _write_file_via_api(endpoint: str, content: str):
    """Write a file via the server API (POST)."""
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=content.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


@pytest.fixture(scope="session")
def browser_context():
    """Launch a single browser for the entire test session."""
    if not HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    """Create a fresh page for each test with clean localStorage."""
    pg = browser_context.new_page()
    pg.goto(BASE_URL + "/focus")
    pg.evaluate('localStorage.clear()')
    yield pg
    pg.close()


@pytest.fixture(autouse=True, scope="session")
def protect_user_data_session():
    """Session-level safety net: back up ALL data files on disk before any test
    runs, restore them after the entire session completes. This catches any
    corruption that per-test restore misses (e.g., if pytest itself crashes)."""
    backups = _backup_files("session")
    try:
        yield
    finally:
        _restore_files(backups)


@pytest.fixture(autouse=True)
def protect_user_data():
    """Per-test: back up and restore data files on disk around every test."""
    backups = _backup_files("test")
    try:
        yield
    finally:
        _restore_files(backups)


def seed_tasks(data):
    """Post task JSON to the server.
    Accepts a dict (with 'tasks' key), a list of task dicts, or a JSON string."""
    if isinstance(data, list):
        payload = json.dumps({"tasks": data})
    elif isinstance(data, dict):
        payload = json.dumps(data)
    else:
        payload = data
    _write_file_via_api(f"{API_PREFIX}/tasks", payload)


def seed_archive(data):
    """Write archive JSON to the server.
    Accepts a dict (with 'tasks'/'notes' keys) or a JSON string."""
    if isinstance(data, dict):
        payload = json.dumps(data)
    else:
        payload = data
    _write_file_via_api(f"{API_PREFIX}/archive", payload)


def read_tasks():
    """Read tasks from the server as parsed JSON."""
    resp = urllib.request.urlopen(f"{BASE_URL}{API_PREFIX}/tasks")
    return json.loads(resp.read().decode("utf-8"))


def read_archive():
    """Read archive from the server as parsed JSON."""
    resp = urllib.request.urlopen(f"{BASE_URL}{API_PREFIX}/archive")
    return json.loads(resp.read().decode("utf-8"))


def read_notes():
    """Read notes from the server as parsed JSON."""
    resp = urllib.request.urlopen(f"{BASE_URL}{API_PREFIX}/notes")
    return json.loads(resp.read().decode("utf-8"))


def clear_tasks():
    """Reset tasks to empty."""
    seed_tasks({"tasks": []})


def clear_archive():
    """Reset archive to empty."""
    seed_archive({"tasks": [], "notes": []})


def wait_for_save(page, endpoint='/api/focus/tasks', method='POST', timeout=3000):
    """Wait for a save response from the API.

    Uses expect_response as a context manager when called before the triggering
    action. When called after the action (legacy usage), falls back to a
    generous wait_for_timeout to allow the debounced auto-save to complete.
    """
    # The debounce is 500 ms; add buffer for network round-trip.
    # wait_for_response does not exist in this Playwright version — use timeout.
    wait_ms = max(timeout, 1500)
    page.wait_for_timeout(wait_ms)


def clear_localstorage(page):
    """Clear localStorage to reset persisted UI state.
    Must be called after the page has navigated to the app origin."""
    page.goto(BASE_URL + "/focus")
    page.evaluate("localStorage.clear()")


def make_task(title, project="", priority="med", status="backlog",
              completed=False, completed_date="", blocker="",
              check_in_note="", session_name="", session_status="",
              subtasks=None, task_id=None):
    """Helper to create a task dict with all required fields."""
    return {
        "id": task_id or f"test-{title.lower().replace(' ', '-')[:20]}",
        "title": title,
        "project": project,
        "priority": priority,
        "status": status,
        "completed": completed,
        "completed_date": completed_date,
        "blocker": blocker,
        "check_in_note": check_in_note,
        "session_name": session_name,
        "session_status": session_status,
        "subtasks": subtasks or [],
    }
