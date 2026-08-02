"""`lb worktree deps` — a worker's own answer to "is my gate honest?"."""

from lumbergh.agent_cli import worktree as worktree_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_deps_requires_a_path(capsys):
    rc = worktree_cli.run("deps", {}, [])
    assert rc == 2
    assert "path" in capsys.readouterr().out


def test_deps_is_quiet_and_zero_when_the_environment_matches_the_code(monkeypatch, capsys):
    monkeypatch.setattr(
        worktree_cli, "_request", lambda _m, _p, **_kw: _Resp({"drift": [], "dep_sync": None})
    )

    rc = worktree_cli.run("deps", {}, ["/wt"])

    assert rc == 0
    assert "ok" in capsys.readouterr().out


def test_deps_exits_nonzero_and_names_the_fix_when_deps_drifted(monkeypatch, capsys):
    """Non-zero is the point: a worker can put this in front of its gate and have the
    gate refuse to be trusted, rather than passing against the shared environment."""
    monkeypatch.setattr(
        worktree_cli,
        "_request",
        lambda _m, _p, **_kw: _Resp(
            {
                "drift": [
                    {"link": "backend/.venv", "manifests": ["backend/pyproject.toml"]},
                ],
                "dep_sync": "uv sync",
            }
        ),
    )

    rc = worktree_cli.run("deps", {}, ["/wt"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "backend/.venv" in out
    assert "backend/pyproject.toml" in out
    assert "uv sync" in out  # tells the worker exactly how to make its gate honest
