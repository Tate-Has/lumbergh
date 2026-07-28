import lumbergh.session_attention as sa
from lumbergh.routers.sessions import get_session_status


def setup_function():
    sa.reset()


def test_status_includes_unseen_fields():
    sa.mark_attention("s", "idle")
    result = get_session_status("s")
    assert result["unseen"] is True
    assert result["attentionState"] == "idle"


def test_status_defaults_when_seen():
    result = get_session_status("never-flagged")
    assert result["unseen"] is False
    assert result["attentionState"] is None
