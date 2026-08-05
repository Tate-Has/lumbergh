"""Two runs that become ready together must be landable as one build.

`lb land --run a --onto dev` leaves `batch-a` as a purely *local* branch, and `--onto`
resolves against the remote — so `lb land --run b --onto batch-a` fails with "couldn't
find remote ref". Lands could not compose, and the whole point of the model is N workers
→ one push → one CI build.
"""

import subprocess

import pytest
from fastapi import HTTPException

from lumbergh import runs
from lumbergh.agent_cli import main as cli
from lumbergh.routers import bill


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _rev(repo, ref):
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()


@pytest.fixture
def two_runs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "dev")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    origin = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", "-q", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "-q", "origin")
    for name in ("solo-925", "solo-935"):
        _git(repo, "checkout", "-q", "-b", name, "dev")
        (repo / f"{name}.txt").write_text(name)
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", name)
    _git(repo, "checkout", "-q", "dev")

    by_run = {
        "port-925": [
            {
                "parent_repo": str(repo),
                "path": str(tmp_path / "wt"),
                "branch": "solo-925",
                "target": "a:solo-925",
            }
        ],
        "port-935": [
            {
                "parent_repo": str(repo),
                "path": str(tmp_path / "wt"),
                "branch": "solo-935",
                "target": "b:solo-935",
            }
        ],
    }
    monkeypatch.setattr(bill, "run_members", lambda r: by_run.get(r, []))
    return repo


def test_batch_branch_names_the_whole_run_set():
    assert runs.batch_branch(["port-925"]) == "batch-port-925"
    assert runs.batch_branch(["port-925", "port-935"]) == "batch-port-925+port-935"


def test_normalize_keeps_the_operators_order_and_drops_repeats():
    # Order is the cherry-pick order, so it is the operator's to choose — but landing the
    # same run twice would cherry-pick every one of its commits twice.
    assert runs.normalize(["b", "a", "b"]) == ["b", "a"]
    assert runs.normalize("solo") == ["solo"]


def test_land_assembles_two_runs_into_one_batch(two_runs):
    repo = two_runs
    resp = bill.land_run(bill.LandBody(run=["port-925", "port-935"], onto="dev", skip_smoke=True))
    assert resp["batch"] == "batch-port-925+port-935"
    assert sorted(resp["picked"]) == ["solo-925", "solo-935"]
    files = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "--name-only", "batch-port-925+port-935"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.split()
    assert "solo-925.txt" in files
    assert "solo-935.txt" in files


def test_two_runs_land_in_a_single_push(two_runs):
    repo = two_runs
    bill.land_run(bill.LandBody(run=["port-925", "port-935"], onto="dev", skip_smoke=True))
    gated = _rev(repo, "batch-port-925+port-935")
    resp = bill.land_run(
        bill.LandBody(run=["port-925", "port-935"], onto="dev", push=True, skip_smoke=True)
    )
    assert resp["pushed"] is True
    assert _rev(repo, "origin/dev") == gated


@pytest.mark.usefixtures("two_runs")
def test_land_reports_every_run_it_covered():
    resp = bill.land_run(bill.LandBody(run=["port-925", "port-935"], onto="dev", skip_smoke=True))
    assert resp["run"] == "port-925+port-935"
    assert resp["runs"] == ["port-925", "port-935"]


@pytest.mark.usefixtures("two_runs")
def test_an_empty_run_in_the_set_is_named_not_silently_dropped():
    with pytest.raises(HTTPException) as raised:
        bill.land_run(bill.LandBody(run=["port-925", "nope"], onto="dev", skip_smoke=True))
    assert "nope" in raised.value.detail["error"]


def test_cli_collects_a_repeated_run_flag():
    _, flags, _, err = cli._parse(["land", "--run", "a", "--run", "b", "--onto", "dev"])
    assert err is None
    assert flags["--run"] == ["a", "b"]
    assert flags["--onto"] == "dev"


def test_cli_single_run_flag_still_collects_a_list():
    _, flags, _, _ = cli._parse(["land", "--run", "a"])
    assert flags["--run"] == ["a"]


def test_spawn_run_flag_is_not_repeatable():
    _, flags, _, _ = cli._parse(["spawn", "--run", "a"])
    assert flags["--run"] == "a"


def test_teardown_drops_a_combined_batch_branch(two_runs, monkeypatch):
    repo = two_runs
    bill.land_run(bill.LandBody(run=["port-925", "port-935"], onto="dev", skip_smoke=True))
    assert _rev(repo, "batch-port-925+port-935")

    monkeypatch.setattr(bill.worktrees, "reap", lambda *_a, **_k: {"status": "removed"})
    monkeypatch.setattr(bill, "kill_tmux_window", lambda _t: True)
    monkeypatch.setattr(bill, "kill_tmux_session", lambda _t: True)
    monkeypatch.setattr(bill.worktrees, "reap_readiness", lambda *_a, **_k: {"processes": []})
    bill.teardown(bill.TeardownBody(run=["port-925", "port-935"]))
    assert _rev(repo, "batch-port-925+port-935") == ""
