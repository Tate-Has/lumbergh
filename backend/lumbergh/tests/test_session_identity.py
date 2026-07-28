from lumbergh.session_identity import Identity, key, prune, read, write


def _ident(**kw):
    base = {
        "session_id": "s1",
        "transcript_path": "/t/x.jsonl",
        "cwd": "/work",
        "source": "startup",
        "written_at": 1.0,
    }
    base.update(kw)
    return Identity(**base)


def test_write_then_read_round_trip(tmp_path):
    write("my-sess", _ident(), store=tmp_path)
    got = read("my-sess", store=tmp_path)
    assert got is not None
    assert got.session_id == "s1"
    assert got.transcript_path == "/t/x.jsonl"
    assert got.source == "startup"


def test_read_missing_returns_none(tmp_path):
    assert read("nope", store=tmp_path) is None


def test_read_malformed_returns_none(tmp_path):
    (tmp_path / f"{key('bad')}.json").write_text("{not json")
    assert read("bad", store=tmp_path) is None


def test_key_is_filename_safe():
    assert key("a/b c:d") == "a_b_c_d"
    assert key("plain-name_1") == "plain-name_1"


def test_prune_removes_only_dead_sessions(tmp_path):
    write("alive", _ident(), store=tmp_path)
    write("dead", _ident(), store=tmp_path)
    prune({"alive"}, store=tmp_path)
    assert read("alive", store=tmp_path) is not None
    assert read("dead", store=tmp_path) is None
