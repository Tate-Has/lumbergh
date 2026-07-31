import pytest

from lumbergh.briefs import enumerate_briefs


def test_directory_globs_md_files_sorted(tmp_path):
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "note.txt").write_text("x")
    result = enumerate_briefs([str(tmp_path)])
    assert [stem for _, stem in result] == ["a", "b"]


def test_explicit_file_list(tmp_path):
    p1 = tmp_path / "kb-1.md"
    p1.write_text("1")
    p2 = tmp_path / "kb-2.md"
    p2.write_text("2")
    result = enumerate_briefs([str(p1), str(p2)])
    assert [stem for _, stem in result] == ["kb-1", "kb-2"]


def test_missing_path_raises(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        enumerate_briefs([str(tmp_path / "nope.md")])


def test_duplicate_stems_raise(tmp_path):
    d1 = tmp_path / "a"
    d1.mkdir()
    (d1 / "x.md").write_text("1")
    d2 = tmp_path / "b"
    d2.mkdir()
    (d2 / "x.md").write_text("2")
    with pytest.raises(ValueError, match="duplicate"):
        enumerate_briefs([str(d1 / "x.md"), str(d2 / "x.md")])


def test_illegal_stem_raises(tmp_path):
    bad = tmp_path / "has space.md"
    bad.write_text("x")
    with pytest.raises(ValueError, match="name"):
        enumerate_briefs([str(bad)])
