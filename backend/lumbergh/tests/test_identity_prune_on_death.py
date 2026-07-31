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


async def test_prune_keeps_full_window_targets(monkeypatch):
    """Identity is keyed by the full session:window target (that's what the pane's
    LUMBERGH_SESSION is set to), so prune must be handed full targets. Reducing to
    the bare session name deletes every batch worker's identity on the next poll,
    which is what forced outcome reads onto the fragile cwd-guess fallback.
    """
    monitor = im.IdleMonitor()
    monkeypatch.setattr(im, "discover_live_targets", lambda: ["batch:w1", "batch:w2"])
    monkeypatch.setattr(im, "_live_session_names", lambda: ["batch"])
    pruned = {}
    monkeypatch.setattr(
        im.session_identity, "prune", lambda live: pruned.setdefault("live", set(live))
    )

    async def _noop(_name):
        return None

    monkeypatch.setattr(monitor, "_check_session", _noop)
    await monitor._check_all_sessions()
    assert pruned["live"] == {"batch:w1", "batch:w2"}
