"""Concurrent access to a shared TinyDB file.

``_get_cached_db`` hands every caller one process-wide TinyDB, so every FastAPI
worker thread shares a single file handle. ``JSONStorage.write`` seeks to 0,
writes, and only then truncates — against a file position that is shared state.
These tests pin down what that has to survive.
"""

import json
import threading
import time

import pytest
import tinydb.storages

from lumbergh import db_utils


@pytest.fixture
def interleaved_dumps(monkeypatch):
    """Force writers to overlap.

    ``JSONStorage.write`` seeks to 0 *before* serializing, so a slow serializer
    parks every writer at offset 0 together and makes the race deterministic
    rather than a matter of timing luck.
    """
    real_dumps = tinydb.storages.json.dumps

    def slow_dumps(*args, **kwargs):
        time.sleep(0.05)
        return real_dumps(*args, **kwargs)

    monkeypatch.setattr(tinydb.storages.json, "dumps", slow_dumps)


def _insert_concurrently(db, count):
    ready = threading.Barrier(count)

    def insert(n):
        ready.wait()
        db.insert({"who": n, "payload": "x" * 200})

    threads = [threading.Thread(target=insert, args=(n,)) for n in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


@pytest.mark.usefixtures("interleaved_dumps")
def test_concurrent_writes_leave_one_json_document(tmp_path):
    path = tmp_path / "worktrees.json"
    _insert_concurrently(db_utils._get_cached_db(path), 4)

    json.loads(path.read_text())


@pytest.mark.usefixtures("interleaved_dumps")
def test_concurrent_writes_do_not_lose_documents(tmp_path):
    path = tmp_path / "worktrees.json"
    db = db_utils._get_cached_db(path)

    _insert_concurrently(db, 4)

    assert sorted(row["who"] for row in db.all()) == [0, 1, 2, 3]


def test_read_recovers_from_concatenated_documents(tmp_path):
    """A file corrupted by an earlier interleave must not 500 forever.

    The prefix document is the complete write that landed at offset 0; the tail
    is a shorter, staler document left behind by the losing writer.
    """
    path = tmp_path / "worktrees.json"
    live = {"_default": {"1": {"path": "/keep"}, "2": {"path": "/keep-too"}}}
    stale = {"_default": {"1": {"path": "/keep"}}}
    path.write_text(json.dumps(live) + json.dumps(stale))

    rows = db_utils._get_cached_db(path).all()

    assert sorted(row["path"] for row in rows) == ["/keep", "/keep-too"]
    json.loads(path.read_text())
