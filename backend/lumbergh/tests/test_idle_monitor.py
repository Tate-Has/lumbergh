"""
Tests for IdleMonitor persistence and DB recovery.

The fork's idle classification logic lives in ``IdleDetector`` and is
covered by :mod:`test_idle_detector`. This module covers the monitor's
persistence path -- specifically that the TinyDB write self-heals when
the on-disk file has been corrupted by an interrupted concurrent write.
"""

import json

import pytest

from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import IdleMonitor


def test_recover_session_data_db_trims_trailing_garbage(tmp_path, monkeypatch):
    """Trailing-garbage corruption from interleaved writes must be recoverable."""
    from lumbergh import constants, db_utils

    monkeypatch.setattr(constants, "SESSIONS_DATA_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "SESSIONS_DATA_DIR", tmp_path)

    valid = {"_default": {"1": {"state": "idle"}}, "extra": {"1": {"hello": "world"}}}
    path = tmp_path / "s-garbage.json"
    path.write_text(json.dumps(valid) + '}}}stray garbage from prior write")"}}}')

    assert db_utils.recover_session_data_db("s-garbage") is True

    recovered = json.loads(path.read_text())
    assert recovered == valid


def test_recover_session_data_db_resets_unrecoverable_file(tmp_path, monkeypatch):
    """Totally corrupt files are backed up and replaced with an empty DB."""
    from lumbergh import constants, db_utils

    monkeypatch.setattr(constants, "SESSIONS_DATA_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "SESSIONS_DATA_DIR", tmp_path)

    path = tmp_path / "s-broken.json"
    path.write_text("definitely not json at all {{{")

    assert db_utils.recover_session_data_db("s-broken") is True

    assert json.loads(path.read_text()) == {}
    backups = list(tmp_path.glob("s-broken.json.corrupt-*"))
    assert len(backups) == 1
    assert "not json" in backups[0].read_text()


@pytest.mark.asyncio
async def test_persist_state_self_heals_corrupt_db(tmp_path, monkeypatch):
    """A corrupt DB file should not block future idle-state persistence."""
    from lumbergh import constants, db_utils

    monkeypatch.setattr(constants, "SESSIONS_DATA_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "SESSIONS_DATA_DIR", tmp_path)

    path = tmp_path / "s-corrupt.json"
    path.write_text('{"todos": {"1": {"items": []}}}trailing junk}}}')

    mon = IdleMonitor()
    await mon._persist_state("s-corrupt", SessionState.IDLE)

    data = json.loads(path.read_text())
    assert "idle_state" in data
    idle_rows = list(data["idle_state"].values())
    assert any(row.get("state") == "idle" for row in idle_rows)
    assert data.get("todos") == {"1": {"items": []}}
