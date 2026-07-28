from lumbergh.routers.settings import SettingsUpdate, _get_defaults, _validate_updates


def test_default_is_opt_out():
    assert _get_defaults()["questionDetectionEnabled"] is False


def test_update_passes_through():
    update_data = _validate_updates(SettingsUpdate(questionDetectionEnabled=True))
    assert update_data["questionDetectionEnabled"] is True


def test_absent_field_not_written():
    update_data = _validate_updates(SettingsUpdate(showSessionDots=False))
    assert "questionDetectionEnabled" not in update_data
