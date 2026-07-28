import lumbergh.session_attention as sa


def setup_function():
    sa.reset()


def test_transition_without_viewer_marks_unseen():
    sa.mark_attention("s", "idle")
    assert sa.is_unseen("s") is True
    assert sa.get("s") == "idle"
    assert sa.unseen_count() == 1


def test_transition_with_viewer_does_not_mark():
    sa.set_viewing("s", True)
    sa.mark_attention("s", "idle")
    assert sa.is_unseen("s") is False
    assert sa.unseen_count() == 0


def test_viewing_clears_existing_unseen():
    sa.mark_attention("s", "blocked")
    assert sa.is_unseen("s") is True
    sa.set_viewing("s", True)
    assert sa.is_unseen("s") is False


def test_leaving_attention_state_clears():
    sa.mark_attention("s", "idle")
    sa.clear_unseen("s")
    assert sa.is_unseen("s") is False


def test_stop_viewing_does_not_reflag():
    sa.set_viewing("s", True)
    sa.mark_attention("s", "idle")
    sa.set_viewing("s", False)
    assert sa.is_unseen("s") is False


def test_snapshot_shape():
    sa.mark_attention("a", "error")
    snap = sa.snapshot()
    assert snap["a"] == {"unseen": True, "attentionState": "error"}


def test_persist_and_load_round_trip(tmp_path):
    path = tmp_path / "attn.json"
    sa.mark_attention("a", "idle")
    sa.mark_attention("b", "blocked")
    sa._write(path)
    sa.reset()
    assert sa.unseen_count() == 0
    sa.load(path)
    assert sa.get("a") == "idle"
    assert sa.get("b") == "blocked"


def test_load_missing_file_is_noop(tmp_path):
    sa.load(tmp_path / "nope.json")
    assert sa.unseen_count() == 0
