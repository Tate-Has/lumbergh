"""
Focus Workspace router — task management, archive, and notes.

Serves the Focus Workspace data at /api/focus/* endpoints.
All data lives in ~/.config/lumbergh/focus/ as TinyDB JSON files.
"""

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response

from lumbergh.db_utils import get_focus_archive_db, get_focus_notes_db, get_focus_tasks_db
from lumbergh.focus_export import archive_to_markdown, tasks_to_markdown
from lumbergh.models import FocusArchiveData, FocusNotesData, FocusTaskList

router = APIRouter(prefix="/api/focus", tags=["focus"])


# ── Tasks ──


@router.get("/tasks")
def get_tasks():
    db = get_focus_tasks_db()
    try:
        all_docs = db.table("_default").all()
        if not all_docs:
            return {"tasks": []}
        return {"tasks": dict(all_docs[0]).get("tasks", [])}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.post("/tasks")
def save_tasks(payload: FocusTaskList):
    db = get_focus_tasks_db()
    try:
        table = db.table("_default")
        table.truncate()
        table.insert(payload.model_dump())
        return Response(content="ok", media_type="text/plain")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.get("/tasks/export")
def export_tasks():
    db = get_focus_tasks_db()
    try:
        all_docs = db.table("_default").all()
        data = dict(all_docs[0]) if all_docs else {"tasks": []}
        md = tasks_to_markdown(data)
        return PlainTextResponse(md)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


# ── Archive ──


@router.get("/archive")
def get_archive():
    db = get_focus_archive_db()
    try:
        all_docs = db.table("_default").all()
        if not all_docs:
            return {"tasks": [], "notes": []}
        doc = dict(all_docs[0])
        return {"tasks": doc.get("tasks", []), "notes": doc.get("notes", [])}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.post("/archive")
def save_archive(payload: FocusArchiveData):
    db = get_focus_archive_db()
    try:
        table = db.table("_default")
        table.truncate()
        table.insert(payload.model_dump())
        return Response(content="ok", media_type="text/plain")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.get("/archive/export")
def export_archive():
    db = get_focus_archive_db()
    try:
        all_docs = db.table("_default").all()
        data = dict(all_docs[0]) if all_docs else {"tasks": [], "notes": []}
        md = archive_to_markdown(data)
        return PlainTextResponse(md)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


# ── Notes ──


@router.get("/notes")
def get_notes():
    db = get_focus_notes_db()
    try:
        all_docs = db.table("_default").all()
        if not all_docs:
            return {"content": ""}
        return {"content": dict(all_docs[0]).get("content", "")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.post("/notes")
def save_notes(payload: FocusNotesData):
    db = get_focus_notes_db()
    try:
        table = db.table("_default")
        table.truncate()
        table.insert(payload.model_dump())
        return Response(content="ok", media_type="text/plain")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.get("/notes/export")
def export_notes():
    db = get_focus_notes_db()
    try:
        all_docs = db.table("_default").all()
        data = dict(all_docs[0]) if all_docs else {"content": ""}
        return PlainTextResponse(data.get("content", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


# ── Migration ──

_FOCUS_FILES = ["tasks.json", "archive.json", "notes.json"]
_DEFAULT_SOURCE_DIR = Path.home() / "src" / "work" / "workstation"


def _has_data(path: Path) -> bool:
    """Return True if the file exists and contains non-empty TinyDB data."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        return bool(data.get("_default", {}))
    except Exception:
        return False


@router.post("/migrate")
def migrate_data(source_dir: str = ""):
    """One-time migration of Focus data from standalone workstation.

    Copies tasks.json, archive.json, and notes.json from the source
    directory to ~/.config/lumbergh/focus/. Files are skipped when the
    target already contains data, so this endpoint is safe to call
    multiple times.
    """
    src_path = Path(source_dir).expanduser().resolve() if source_dir else _DEFAULT_SOURCE_DIR

    if not src_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Source directory does not exist: {src_path}",
        )

    from lumbergh.constants import FOCUS_DIR

    target_dir: Path = FOCUS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}
    for name in _FOCUS_FILES:
        src_file = src_path / name
        dst_file = target_dir / name

        if not src_file.exists():
            results[name] = "source not found"
            continue

        if _has_data(dst_file):
            results[name] = "skipped (target exists)"
            continue

        shutil.copy2(src_file, dst_file)
        results[name] = "migrated"

    return results
