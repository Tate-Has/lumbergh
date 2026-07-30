import pytest
from fastapi import HTTPException

from lumbergh.routers.settings import (
    BillSettings,
    SettingsUpdate,
    _get_defaults,
    _validate_updates,
)


def test_defaults_include_a_full_bill_block():
    b = _get_defaults()["bill"]
    assert b == {"harness": "pi", "personality": "professional", "customPersonality": ""}


def test_preset_personality_passes_through():
    data = _validate_updates(SettingsUpdate(bill=BillSettings(personality="lumbergh")))
    assert data["bill"] == {"personality": "lumbergh"}


def test_custom_personality_and_harness_pass_through():
    data = _validate_updates(
        SettingsUpdate(
            bill=BillSettings(personality="custom", customPersonality="arr", harness="claude-code")
        )
    )
    assert data["bill"] == {
        "personality": "custom",
        "customPersonality": "arr",
        "harness": "claude-code",
    }


def test_unknown_personality_is_rejected():
    with pytest.raises(HTTPException):
        _validate_updates(SettingsUpdate(bill=BillSettings(personality="pirate")))


def test_unknown_harness_is_rejected():
    with pytest.raises(HTTPException):
        _validate_updates(SettingsUpdate(bill=BillSettings(harness="nope")))


def test_overlong_custom_personality_is_rejected():
    with pytest.raises(HTTPException):
        _validate_updates(
            SettingsUpdate(bill=BillSettings(personality="custom", customPersonality="x" * 4001))
        )


def test_absent_bill_is_not_written():
    data = _validate_updates(SettingsUpdate(showSessionDots=False))
    assert "bill" not in data
