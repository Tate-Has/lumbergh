import lumbergh.agent_cli.main as cli
from lumbergh.agent_cli import skill


def test_committed_skill_matches_source():
    # CI drift guard: the committed SKILL.md must equal the canonical string.
    assert skill.check() is True
    assert skill.committed_path().read_text() == skill.SKILL_MD


def test_install_writes_and_is_idempotent(tmp_path):
    written = skill.install([tmp_path])
    target = tmp_path / "lb" / "SKILL.md"
    assert written == [target]
    assert target.read_text() == skill.SKILL_MD
    skill.install([tmp_path])  # idempotent — content unchanged
    assert target.read_text() == skill.SKILL_MD


def _run(monkeypatch, argv):
    out = []
    monkeypatch.setattr(cli, "_emit", out.append)
    code = cli.main(argv)
    return code, "\n".join(out)


def test_lb_skill_prints_doc(monkeypatch):
    code, out = _run(monkeypatch, ["skill"])
    assert code == 0
    assert "name: lb" in out
    assert "# lb — drive Lumbergh sessions" in out


def test_lb_skill_check(monkeypatch):
    code, out = _run(monkeypatch, ["skill", "--check"])
    assert code == 0
    assert "up to date" in out


def test_lb_skill_install_reports_targets(monkeypatch, tmp_path):
    monkeypatch.setattr(skill, "detect_dirs", lambda: [tmp_path])
    code, out = _run(monkeypatch, ["skill", "install"])
    assert code == 0
    assert "installed[1]{path}:" in out
    assert (tmp_path / "lb" / "SKILL.md").exists()


def test_lb_skill_install_no_dirs(monkeypatch):
    monkeypatch.setattr(skill, "detect_dirs", list)
    code, out = _run(monkeypatch, ["skill", "install"])
    assert code == 0
    assert "no agent skill directories" in out
