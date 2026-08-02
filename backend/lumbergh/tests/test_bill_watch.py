import pytest

from lumbergh import babysit, bill_watch


@pytest.fixture(autouse=True)
def _registries(tmp_path, monkeypatch):
    monkeypatch.setattr(bill_watch, "WATCH_PATH", tmp_path / "bill_watch.json")
    monkeypatch.setattr(babysit, "BABYSITS_PATH", tmp_path / "babysits.json")


def test_an_unengaged_session_is_not_watched():
    assert bill_watch.watched() == set()


def test_engaging_a_session_puts_it_under_watch():
    bill_watch.engage("port", "2026-08-02T20:00:00+00:00")
    assert bill_watch.watched() == {"port"}


def test_releasing_ends_the_watch():
    bill_watch.engage("port", "2026-08-02T20:00:00+00:00")
    assert bill_watch.release("port") is True
    assert bill_watch.watched() == set()
    assert bill_watch.release("port") is False


def test_a_babysat_session_is_watched_without_engagement():
    babysit.start("port", "/repo/port", "2026-08-02T20:00:00+00:00")
    assert bill_watch.watched() == {"port"}


def test_releasing_never_ends_a_babysit():
    babysit.start("port", "/repo/port", "2026-08-02T20:00:00+00:00")
    bill_watch.engage("port", "2026-08-02T20:00:00+00:00")
    bill_watch.release("port")
    assert bill_watch.watched() == {"port"}, "the standing babysit outlives the one-shot"


def test_engagements_survive_a_reload():
    bill_watch.engage("port", "2026-08-02T20:00:00+00:00")
    assert bill_watch.engaged() == {"port"}
    assert bill_watch.WATCH_PATH.exists()


def test_prune_drops_engagements_for_sessions_that_are_gone():
    bill_watch.engage("port", "2026-08-02T20:00:00+00:00")
    bill_watch.engage("aio", "2026-08-02T20:00:00+00:00")
    bill_watch.prune({"port"})
    assert bill_watch.engaged() == {"port"}


def test_a_corrupt_registry_reads_as_empty():
    bill_watch.WATCH_PATH.write_text("{not json")
    assert bill_watch.engaged() == set()
