from lumbergh.worktrees import read_land_smoke


def test_reads_land_smoke(tmp_path):
    (tmp_path / ".lumbergh.toml").write_text('[land]\nsmoke = "uv run pytest -q"\n')
    assert read_land_smoke(tmp_path) == "uv run pytest -q"


def test_none_when_absent(tmp_path):
    (tmp_path / ".lumbergh.toml").write_text("[worktree]\nlinks = []\n")
    assert read_land_smoke(tmp_path) is None


def test_none_when_no_dotfile(tmp_path):
    assert read_land_smoke(tmp_path) is None
