from lumbergh.routers.settings import SettingsUpdate, _get_defaults, _validate_updates


def test_default_is_opt_out_of_the_literal_control_v():
    """Ships on: xterm's default silently breaks every clipboard-injection tool."""
    assert _get_defaults()["ctrlVPastes"] is True


def test_update_passes_through():
    update_data = _validate_updates(SettingsUpdate(ctrlVPastes=False))
    assert update_data["ctrlVPastes"] is False


def test_absent_field_not_written():
    update_data = _validate_updates(SettingsUpdate(showSessionDots=False))
    assert "ctrlVPastes" not in update_data
