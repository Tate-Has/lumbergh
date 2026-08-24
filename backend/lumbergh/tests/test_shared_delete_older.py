"""Bulk deletion of shared files older than a cutoff."""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from lumbergh.main import app

    return TestClient(app)


@pytest.fixture
def shared_dir(temp_dir, monkeypatch):
    d = temp_dir / "shared"
    d.mkdir()
    monkeypatch.setattr("lumbergh.routers.shared.SHARED_DIR", d)
    return d


def write_at(shared_dir, name, mtime):
    path = shared_dir / name
    path.write_text(name)
    os.utime(path, (mtime, mtime))
    return path


class TestDeleteOlderThan:
    def test_deletes_only_files_older_than_cutoff(self, client, shared_dir):
        write_at(shared_dir, "fresh.md", 2000)
        write_at(shared_dir, "stale.md", 500)
        write_at(shared_dir, "ancient.md", 100)

        r = client.delete("/api/shared/files?older_than=1000")

        assert r.status_code == 200
        assert r.json()["deleted"] == 2
        assert [f.name for f in shared_dir.iterdir()] == ["fresh.md"]

    def test_file_exactly_at_cutoff_survives(self, client, shared_dir):
        write_at(shared_dir, "boundary.md", 1000)

        r = client.delete("/api/shared/files?older_than=1000")

        assert r.json()["deleted"] == 0
        assert (shared_dir / "boundary.md").exists()

    def test_without_cutoff_everything_goes(self, client, shared_dir):
        write_at(shared_dir, "fresh.md", 2000)
        write_at(shared_dir, "stale.md", 500)

        r = client.delete("/api/shared/files")

        assert r.json()["deleted"] == 2
        assert list(shared_dir.iterdir()) == []
