from lumbergh.idle_monitor import idle_monitor
from lumbergh.routers.sessions import get_session_status


def setup_function():
    idle_monitor._needs_answer.clear()


def test_status_defaults_when_no_question():
    result = get_session_status("never-flagged")
    assert result["needsAnswer"] is False
    assert result["needsAnswerReason"] is None


def test_status_reflects_needs_answer():
    idle_monitor._needs_answer["s"] = "choose a database"
    result = get_session_status("s")
    assert result["needsAnswer"] is True
    assert result["needsAnswerReason"] == "choose a database"
