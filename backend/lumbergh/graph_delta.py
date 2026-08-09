"""Incremental git-graph updates.

The frontend re-requests the graph every few seconds. On a busy repo the
payload is hundreds of commits and only a handful of them have moved, so the
overwhelming majority of every response is bytes the client already has.

The client holds a ``version`` from its last response and offers it back as a
cursor. Three answers are possible:

``unchanged``
    the version still matches — nothing is sent

``delta``
    the cursor is one we still remember — send the commits the client lacks,
    plus the order the full list should end up in

``reset``
    the cursor is too old, or from another session, or the server restarted —
    send a whole keyframe and let the client start over

The reset branch is what keeps this safe. Anything the server cannot explain
cheaply degrades to today's behaviour rather than to a subtly wrong graph.
"""

from collections import OrderedDict

# Deltas are only useful against a recent cursor; a client that has been away
# longer than this is cheaper to re-seed than to reconcile.
DEFAULT_RETAIN = 12

# Fields small enough that syncing them incrementally would cost more in bugs
# than it saves in bytes. They ride along whole on every delta.
WHOLE_FIELDS = ("branches", "head", "workingChanges", "worktrees", "mine")


class GraphHistory:
    """Remembers the commit ordering behind recent versions, per session."""

    def __init__(self, retain: int = DEFAULT_RETAIN):
        self._retain = retain
        self._by_session: dict[str, OrderedDict[str, list[str]]] = {}

    def record(self, session: str, version: str, order: list[str]) -> None:
        versions = self._by_session.setdefault(session, OrderedDict())
        if version in versions:
            versions.move_to_end(version)
        else:
            versions[version] = order
        while len(versions) > self._retain:
            versions.popitem(last=False)

    def order_for(self, session: str, version: str) -> list[str] | None:
        versions = self._by_session.get(session)
        return versions.get(version) if versions else None

    def forget(self, session: str) -> None:
        self._by_session.pop(session, None)


def build_response(
    payload: dict,
    since: str | None,
    history: GraphHistory,
    session: str,
) -> dict:
    """Turn a freshly computed graph into the smallest correct response."""
    version = payload["version"]
    order = [commit["hash"] for commit in payload["commits"]]
    history.record(session, version, order)

    if since == version:
        return {"version": version, "unchanged": True}

    known = history.order_for(session, since) if since else None
    if known is None:
        return payload if since is None else {**payload, "reset": True}

    have = set(known)
    added = [c for c in payload["commits"] if c["hash"] not in have]
    response = {
        "version": version,
        "delta": True,
        "added": added,
        # A commit's identity is immutable but two of its fields are not: a
        # branch badge moves off a commit when the branch advances, and
        # ``pushed`` flips when work is pushed. Sending them only on ``added``
        # leaves the client rendering a stale badge on every commit that was
        # ever a branch tip — they pile up for as long as the view is open.
        # Both are sparse, so shipping them whole costs almost nothing.
        "refs": {c["hash"]: c["refs"] for c in payload["commits"] if c.get("refs")},
        **_push_state(payload["commits"]),
        **{field: payload[field] for field in WHOLE_FIELDS if field in payload},
    }

    keep = _reconstructable_from(order, known, [c["hash"] for c in added])
    if keep is None:
        response["order"] = order
    else:
        response["keep"] = keep
    return response


def _push_state(commits: list[dict]) -> dict:
    """Name whichever of pushed/unpushed is the shorter list.

    A branch with no upstream reports every commit as unpushed, so naming the
    unpushed ones cost more than the rest of the delta put together. Whichever
    side is in the minority is the one worth sending; the other is the default.
    """
    unpushed = [c["hash"] for c in commits if not c.get("pushed", True)]
    if len(unpushed) * 2 > len(commits):
        return {"pushed": [c["hash"] for c in commits if c.get("pushed", True)]}
    return {"unpushed": unpushed}


def _reconstructable_from(order: list[str], known: list[str], added: list[str]) -> int | None:
    """How many of the client's own commits survive, if the new order is just
    ``added`` followed by a prefix of what it already had.

    Almost every update has this shape — new commits arrive at the top and the
    oldest fall off the end — and describing it with a single number saves
    re-sending the whole ordering. Anything else (a rebase reordering the
    middle, say) returns ``None`` and gets the explicit list.
    """
    keep = len(order) - len(added)
    if keep < 0 or order[: len(added)] != added or order[len(added) :] != known[:keep]:
        return None
    return keep
