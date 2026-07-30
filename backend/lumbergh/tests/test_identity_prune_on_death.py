import lumbergh.idle_monitor as im


async def test_check_all_sessions_prunes_identity(monkeypatch):
    monitor = im.IdleMonitor()
    monitor._fingerprints = {"dead": "x"}
    monkeypatch.setattr(im, "discover_live_targets", lambda: ["alive"])
    pruned = {}
    monkeypatch.setattr(
        im.session_identity, "prune", lambda live: pruned.setdefault("live", set(live))
    )

    async def _noop(_name):
        return None

    monkeypatch.setattr(monitor, "_check_session", _noop)
    await monitor._check_all_sessions()
    assert pruned["live"] == {"alive"}
