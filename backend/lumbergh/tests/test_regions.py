from lumbergh.detect.regions import extract

ANSI = "\x1b[32m● done\x1b[0m\n\x1b[1mline two\x1b[0m\n\n\n"


def test_recent_strips_ansi_and_trailing_blanks():
    assert extract("recent", ANSI, "") == ["● done", "line two"]


def test_recent_lines_takes_last_n():
    content = "a\nb\nc\nd\n"
    assert extract("recent_lines(2)", content, "") == ["c", "d"]


def test_recent_caps_at_fifteen():
    content = "\n".join(str(i) for i in range(20)) + "\n"
    assert extract("recent", content, "") == [str(i) for i in range(5, 20)]


def test_osc_title_returns_title():
    assert extract("osc_title", "ignored body", "✻ Baking") == ["✻ Baking"]


def test_osc_title_empty_returns_empty_list():
    assert extract("osc_title", "body", "") == []


def test_unknown_region_returns_empty():
    assert extract("bogus", "a\nb\n", "") == []
