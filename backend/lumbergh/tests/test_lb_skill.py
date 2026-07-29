import lumbergh.agent_cli.main as cli
from lumbergh.agent_cli import skill


def test_committed_skills_match_source():
    # CI drift guard: every committed SKILL.md must equal its canonical string.
    assert skill.check() is True
    for name, content in skill.SKILLS.items():
        assert skill.committed_path(name).read_text() == content


def test_install_writes_every_skill_and_is_idempotent(tmp_path):
    written = skill.install([tmp_path])
    for name, content in skill.SKILLS.items():
        target = tmp_path / name / "SKILL.md"
        assert target in written
        assert target.read_text() == content
    skill.install([tmp_path])  # idempotent — content unchanged
    assert (tmp_path / "lb" / "SKILL.md").read_text() == skill.SKILLS["lb"]


def test_install_can_target_a_subset_of_skills(tmp_path):
    written = skill.install([tmp_path], names=["ship", "scout"])
    assert (tmp_path / "ship" / "SKILL.md").exists()
    assert (tmp_path / "scout" / "SKILL.md").exists()
    assert not (tmp_path / "lb").exists()
    assert len(written) == 2


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
    assert f"installed[{len(skill.SKILLS)}]{{path}}:" in out
    assert (tmp_path / "lb" / "SKILL.md").exists()
    assert (tmp_path / "ship" / "SKILL.md").exists()
    assert (tmp_path / "scout" / "SKILL.md").exists()


def test_lb_skill_install_no_dirs(monkeypatch):
    monkeypatch.setattr(skill, "detect_dirs", list)
    code, out = _run(monkeypatch, ["skill", "install"])
    assert code == 0
    assert "no agent skill directories" in out
