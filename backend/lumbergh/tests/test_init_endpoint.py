import tomllib

import pytest
from fastapi import HTTPException

from lumbergh import worktrees
from lumbergh.routers import bill


def _repo(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_init_creates_dotfile_with_default_commit_mode(tmp_path):
    repo = _repo(tmp_path)
    resp = bill.init(bill.InitBody(repo=str(repo)))
    data = tomllib.loads((repo / ".lumbergh.toml").read_text())
    assert data["delivery"]["mode"] == "commit"
    assert resp["created"] is True
    assert "delivery" in resp["added"]


def test_init_honors_explicit_delivery_and_smoke(tmp_path):
    repo = _repo(tmp_path)
    bill.init(bill.InitBody(repo=str(repo), delivery="pr", smoke="./lint.sh"))
    data = tomllib.loads((repo / ".lumbergh.toml").read_text())
    assert data["delivery"]["mode"] == "pr"
    assert data["land"]["smoke"] == "./lint.sh"


def test_init_does_not_clobber_existing_delivery(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".lumbergh.toml").write_text('[delivery]\nmode = "branch"\n')
    resp = bill.init(bill.InitBody(repo=str(repo), delivery="pr"))
    data = tomllib.loads((repo / ".lumbergh.toml").read_text())
    assert data["delivery"]["mode"] == "branch"  # preserved, not overwritten
    assert resp["added"] == []
    assert any("branch" in u for u in resp["unchanged"])


def test_init_appends_land_to_existing_file(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".lumbergh.toml").write_text("[worktree]\nlinks = []\n")
    bill.init(bill.InitBody(repo=str(repo), smoke="make test"))
    data = tomllib.loads((repo / ".lumbergh.toml").read_text())
    assert data["worktree"]["links"] == []  # preserved
    assert data["delivery"]["mode"] == "commit"  # added
    assert data["land"]["smoke"] == "make test"  # added


def test_init_rejects_non_repo(tmp_path):
    with pytest.raises(HTTPException):
        bill.init(bill.InitBody(repo=str(tmp_path)))  # no .git


def test_init_rejects_bad_delivery_mode(tmp_path):
    with pytest.raises(HTTPException):
        bill.init(bill.InitBody(repo=str(_repo(tmp_path)), delivery="yeet"))


def test_init_records_a_dep_sync_command(tmp_path):
    """The one thing that lets `lb land` recover from dependency drift instead of
    refusing — so `lb init` has to be able to write it."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    bill.init(bill.InitBody(repo=str(repo), dep_sync="uv sync --project backend"))

    text = (repo / ".lumbergh.toml").read_text()
    assert "[worktree]" in text
    assert 'dep_sync = "uv sync --project backend"' in text
    assert worktrees.read_dep_sync(repo) == "uv sync --project backend"


def test_init_leaves_an_existing_worktree_table_alone(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".lumbergh.toml").write_text('[worktree]\ndep_sync = "make deps"\n')

    resp = bill.init(bill.InitBody(repo=str(repo), dep_sync="something else"))

    assert worktrees.read_dep_sync(repo) == "make deps"
    assert any("worktree" in u for u in resp["unchanged"])
