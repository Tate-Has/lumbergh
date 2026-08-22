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


def test_viewing_a_session_covers_the_windows_inside_it():
    """A batch session's work is flagged per window, but you open the session."""
    sa.mark_attention("batch:1187", "idle")
    sa.mark_attention("batch:1188", "idle")
    sa.mark_attention("other:1", "idle")

    sa.set_viewing("batch", True)

    assert sa.is_unseen("batch:1187") is False
    assert sa.is_unseen("batch:1188") is False
    assert sa.is_unseen("other:1") is True, "a different session keeps its flag"


def test_clear_session_reaches_the_windows_too():
    sa.mark_attention("batch", "idle")
    sa.mark_attention("batch:1187", "error")

    sa.clear_session("batch")

    assert sa.unseen_count() == 0


def test_a_similarly_named_session_is_not_swept_up():
    sa.mark_attention("batch-two", "idle")

    sa.clear_session("batch")

    assert sa.is_unseen("batch-two") is True


def test_forget_missing_drops_flags_for_sessions_that_are_gone():
    sa.mark_attention("alive", "idle")
    sa.mark_attention("ghost", "idle")

    sa.forget_missing({"alive"})

    assert sa.is_unseen("alive") is True
    assert sa.is_unseen("ghost") is False


def test_forget_missing_keeps_a_window_whose_session_is_alive():
    """`batch:1187` belongs to `batch`; liveness is reported per session."""
    sa.mark_attention("batch:1187", "idle")
    sa.mark_attention("dead-batch:1", "idle")

    sa.forget_missing({"batch"})

    assert sa.is_unseen("batch:1187") is True
    assert sa.is_unseen("dead-batch:1") is False


def test_forget_missing_leaves_viewers_alone():
    sa.set_viewing("alive", True)
    sa.forget_missing({"alive"})
    sa.mark_attention("alive", "idle")

    assert sa.is_unseen("alive") is False
