"""A worker that changes dependencies must not gate against the shared checkout's.

Worktrees symlink `.venv`/`node_modules` to the main checkout — deliberate, and right
until a worker changes a manifest, at which point its lint and tests exercise the wrong
versions and pass anyway. Silent-and-green is the state these tests exist to prevent.
"""

import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from lumbergh import worktrees
from lumbergh.routers import bill


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo_with_linked_venv(tmp_path):
    repo = tmp_path / "repo"
    (repo / "backend").mkdir(parents=True)
    _git(repo.parent, "init", "-q", "-b", "master", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / ".gitignore").write_text("backend/.venv\n")
    (repo / ".lumbergh.toml").write_text('[worktree]\nlinks = ["backend/.venv"]\n')
    (repo / "backend" / "pyproject.toml").write_text('deps = ["mcp==1.29.0"]\n')
    (repo / "backend" / ".venv").mkdir()
    (repo / "backend" / ".venv" / "installed").write_text("mcp 1.29.0")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    origin = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", "-q", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "-q", "origin")
    return repo


def _worker_changing_deps(repo: Path, branch: str) -> None:
    _git(repo, "checkout", "-q", "-b", branch, "master")
    (repo / "backend" / "pyproject.toml").write_text('deps = ["mcp==2.0.0"]\n')
    _git(repo, "commit", "-qam", f"{branch}: migrate to mcp 2")
    _git(repo, "checkout", "-q", "master")


def _worker_changing_code(repo: Path, branch: str) -> None:
    _git(repo, "checkout", "-q", "-b", branch, "master")
    (repo / "backend" / "app.py").write_text("# touches no manifest\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", f"{branch}: a change with no dependency in it")
    _git(repo, "checkout", "-q", "master")


def _register_run(monkeypatch, repo: Path, branch: str) -> None:
    monkeypatch.setattr(
        "lumbergh.worktrees.all_entries",
        lambda: [
            {
                "target": f"sprint:{branch}",
                "branch": branch,
                "parent_repo": str(repo),
                "run": "sprint",
            }
        ],
    )


def test_land_smoke_that_reinstalls_deps_leaves_the_shared_checkout_intact(
    monkeypatch, repo_with_linked_venv
):
    """A gate that reinstalls (`npm ci`, `uv sync`) deletes a dependency directory's
    *contents*, not the directory itself — so through a link it empties the developer's
    own checkout, and passes green while doing it. The next lint in the main checkout is
    the one that fails, for a reason found nowhere in the code being tested."""
    repo = repo_with_linked_venv
    _worker_changing_code(repo, "feat-code")
    _register_run(monkeypatch, repo, "feat-code")

    resp = bill.land_run(
        bill.LandBody(run="sprint", onto="master", push=False, smoke="rm -rf backend/.venv/*")
    )

    assert resp["smoke"] == "passed"
    assert (repo / "backend" / ".venv" / "installed").read_text() == "mcp 1.29.0"


def test_dep_drift_flags_a_symlinked_dep_whose_manifest_changed(tmp_path):
    wt = tmp_path / "wt"
    (wt / "backend").mkdir(parents=True)
    (tmp_path / "real-venv").mkdir()
    (wt / "backend" / ".venv").symlink_to(tmp_path / "real-venv")

    drift = worktrees.dep_drift(wt, ["backend/pyproject.toml"], ["backend/.venv"])

    assert drift == [{"link": "backend/.venv", "manifests": ["backend/pyproject.toml"]}]


def test_dep_drift_ignores_a_manifest_change_in_another_directory(tmp_path):
    wt = tmp_path / "wt"
    (wt / "backend").mkdir(parents=True)
    (tmp_path / "real-venv").mkdir()
    (wt / "backend" / ".venv").symlink_to(tmp_path / "real-venv")

    # A sibling project's manifest says nothing about backend's environment.
    drift = worktrees.dep_drift(wt, ["tools/pyproject.toml"], ["backend/.venv"])

    assert drift == []


def test_dep_drift_is_clear_once_the_dep_dir_is_a_real_directory(tmp_path):
    wt = tmp_path / "wt"
    (wt / "backend" / ".venv").mkdir(parents=True)

    # Not a symlink: the worker owns this environment, so its gate is honest.
    drift = worktrees.dep_drift(wt, ["backend/pyproject.toml"], ["backend/.venv"])

    assert drift == []


def test_land_refuses_a_dep_changing_batch_when_no_resync_is_configured(
    monkeypatch, repo_with_linked_venv
):
    repo = repo_with_linked_venv
    _worker_changing_deps(repo, "feat-deps")
    monkeypatch.setattr(
        "lumbergh.worktrees.all_entries",
        lambda: [
            {
                "target": "sprint:feat-deps",
                "branch": "feat-deps",
                "parent_repo": str(repo),
                "run": "sprint",
            }
        ],
    )

    with pytest.raises(HTTPException) as exc:
        bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, smoke="true"))

    assert exc.value.detail["stage"] == "deps"
    assert "backend/.venv" in exc.value.detail["error"]


def test_land_resyncs_the_drifted_dep_when_the_repo_configures_it(
    monkeypatch, repo_with_linked_venv
):
    repo = repo_with_linked_venv
    (repo / ".lumbergh.toml").write_text(
        '[worktree]\nlinks = ["backend/.venv"]\n'
        'dep_sync = "echo mcp 2.0.0 > backend/.venv/installed"\n'
    )
    _git(repo, "commit", "-qam", "configure dep_sync")
    _worker_changing_deps(repo, "feat-deps")
    monkeypatch.setattr(
        "lumbergh.worktrees.all_entries",
        lambda: [
            {
                "target": "sprint:feat-deps",
                "branch": "feat-deps",
                "parent_repo": str(repo),
                "run": "sprint",
            }
        ],
    )

    smoked = {}

    def fake_smoke(worktree, _cmd):
        smoked["installed"] = (Path(worktree) / "backend" / ".venv" / "installed").read_text()
        smoked["is_symlink"] = (Path(worktree) / "backend" / ".venv").is_symlink()
        return {"ok": True, "returncode": 0}

    monkeypatch.setattr("lumbergh.land.run_smoke", fake_smoke)

    resp = bill.land_run(bill.LandBody(run="sprint", onto="master", push=False, smoke="true"))

    assert resp["deps"] == ["backend/.venv"]
    assert smoked["is_symlink"] is False  # smoke ran against the batch's own environment
    assert smoked["installed"].strip() == "mcp 2.0.0"
    # The shared checkout the worktrees link to is left exactly as it was.
    assert (repo / "backend" / ".venv" / "installed").read_text() == "mcp 1.29.0"
