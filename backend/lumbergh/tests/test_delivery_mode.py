from lumbergh.agent_cli.skill import _SHIP_SKILL_MD
from lumbergh.routers.bill import _brief_delivery
from lumbergh.worktrees import read_delivery_mode


def test_default_mode_is_commit_when_unset(tmp_path):
    assert read_delivery_mode(tmp_path) == "commit"


def test_reads_declared_mode(tmp_path):
    (tmp_path / ".lumbergh.toml").write_text('[delivery]\nmode = "pr"\n')
    assert read_delivery_mode(tmp_path) == "pr"


def test_unknown_mode_falls_back_to_commit(tmp_path):
    (tmp_path / ".lumbergh.toml").write_text('[delivery]\nmode = "yeet"\n')
    assert read_delivery_mode(tmp_path) == "commit"


def test_commit_clause_forbids_push_and_pr(tmp_path):
    msg = _brief_delivery(tmp_path / "b.md", "ship", "w", "commit")
    assert "STOP" in msg
    assert "never push" in msg
    assert "DELIVERED: <sha>" in msg
    assert "gh pr create" not in msg


def test_pr_clause_opens_a_pr(tmp_path):
    msg = _brief_delivery(tmp_path / "b.md", "ship", "w", "pr")
    assert "gh pr create" in msg
    assert "DELIVERED: <pr-url>" in msg


def test_branch_clause_pushes_without_pr(tmp_path):
    msg = _brief_delivery(tmp_path / "b.md", "ship", "w", "branch")
    assert "do NOT open a PR" in msg
    assert "DELIVERED: <branch>" in msg


def test_default_brief_delivery_is_commit(tmp_path):
    assert "STOP" in _brief_delivery(tmp_path / "b.md", "ship", "w")


def test_scout_delivery_unaffected_by_mode(tmp_path):
    msg = _brief_delivery(tmp_path / "b.md", "scout", "w", "commit")
    assert "report" in msg.lower()
    assert "DELIVERED: <where the report is>" in msg


def test_ship_skill_states_all_three_modes():
    for mode in ("**pr**", "**branch**", "**commit**"):
        assert mode in _SHIP_SKILL_MD
