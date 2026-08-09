"""Incremental graph updates.

The graph is re-requested every few seconds and most of the time almost nothing
has moved, so re-sending several hundred commits is nearly all waste. These
tests pin down the three answers the server is allowed to give — unchanged,
delta, or a full keyframe — and the rule that decides between them.
"""

from lumbergh.graph_delta import GraphHistory, build_response


def _payload(hashes, version="v1", **extra):
    return {
        "commits": [{"hash": h, "message": f"commit {h}"} for h in hashes],
        "branches": [],
        "head": {"hash": hashes[0] if hashes else None, "branch": "main"},
        "workingChanges": None,
        "worktrees": [],
        "mine": {"available": True, "active": False},
        "version": version,
        **extra,
    }


class TestBuildResponse:
    def test_without_a_cursor_the_client_gets_a_keyframe(self):
        payload = _payload(["a", "b", "c"])
        history = GraphHistory()

        response = build_response(payload, since=None, history=history, session="s")

        assert response["commits"] == payload["commits"]
        assert "delta" not in response

    def test_matching_cursor_sends_nothing_back(self):
        payload = _payload(["a", "b", "c"], version="v1")
        history = GraphHistory()
        build_response(payload, since=None, history=history, session="s")

        response = build_response(payload, since="v1", history=history, session="s")

        assert response == {"version": "v1", "unchanged": True}

    def test_known_cursor_sends_only_the_new_commits(self):
        history = GraphHistory()
        build_response(_payload(["b", "c"], version="v1"), None, history, "s")

        response = build_response(_payload(["a", "b", "c"], version="v2"), "v1", history, "s")

        assert response["delta"] is True
        assert [c["hash"] for c in response["added"]] == ["a"]
        assert "commits" not in response

    def test_commits_arriving_on_top_need_no_ordering_at_all(self):
        """The overwhelmingly common shape: new at the head, oldest fall off."""
        history = GraphHistory()
        build_response(_payload(["b", "c"], version="v1"), None, history, "s")

        response = build_response(_payload(["a", "b", "c"], version="v2"), "v1", history, "s")

        assert response["keep"] == 2
        assert "order" not in response

    def test_a_change_touching_no_commits_sends_no_commit_data(self):
        """Editing a file moves workingChanges and nothing else."""
        history = GraphHistory()
        build_response(_payload(["a", "b"], version="v1"), None, history, "s")

        response = build_response(
            _payload(["a", "b"], version="v2", workingChanges={"files": 1}),
            "v1",
            history,
            "s",
        )

        assert response["added"] == []
        assert response["keep"] == 2
        assert "order" not in response

    def test_dropped_commits_are_described_by_the_survivor_count(self):
        history = GraphHistory()
        build_response(_payload(["a", "b", "c"], version="v1"), None, history, "s")

        response = build_response(_payload(["a", "b"], version="v2"), "v1", history, "s")

        assert response["added"] == []
        assert response["keep"] == 2

    def test_a_reordering_falls_back_to_the_explicit_list(self):
        """A rebase can shuffle the middle, which no survivor count describes."""
        history = GraphHistory()
        build_response(_payload(["a", "b", "c"], version="v1"), None, history, "s")

        response = build_response(_payload(["c", "b", "a"], version="v2"), "v1", history, "s")

        assert response["order"] == ["c", "b", "a"]
        assert "keep" not in response

    def test_unknown_cursor_forces_a_reset(self):
        history = GraphHistory()

        response = build_response(_payload(["a"], version="v2"), "long-forgotten", history, "s")

        assert response["reset"] is True
        assert [c["hash"] for c in response["commits"]] == ["a"]

    def test_a_rewritten_history_is_still_correct(self):
        """A rebase replaces commits rather than appending them."""
        history = GraphHistory()
        build_response(_payload(["old1", "old2", "base"], version="v1"), None, history, "s")

        response = build_response(
            _payload(["new1", "new2", "base"], version="v2"), "v1", history, "s"
        )

        assert sorted(c["hash"] for c in response["added"]) == ["new1", "new2"]
        # The survivors are not a prefix of what the client held, so the
        # shorthand cannot describe this and the explicit list is sent.
        assert response["order"] == ["new1", "new2", "base"]

    def test_a_delta_restates_where_the_branches_are(self):
        """A badge belongs to the current tip, not to whatever held it before."""
        history = GraphHistory()
        old = _payload(["b"], version="v1")
        old["commits"][0]["refs"] = [{"name": "dev", "local": True, "remote": False}]
        build_response(old, None, history, "s")

        new = _payload(["a", "b"], version="v2")
        new["commits"][0]["refs"] = [{"name": "dev", "local": True, "remote": False}]
        response = build_response(new, "v1", history, "s")

        assert response["refs"] == {"a": [{"name": "dev", "local": True, "remote": False}]}

    def test_a_delta_restates_which_commits_are_unpushed(self):
        history = GraphHistory()
        build_response(_payload(["b"], version="v1"), None, history, "s")

        new = _payload(["a", "b"], version="v2")
        new["commits"][0]["pushed"] = False
        new["commits"][1]["pushed"] = True
        response = build_response(new, "v1", history, "s")

        assert response["unpushed"] == ["a"]

    def test_a_mostly_unpushed_branch_names_the_pushed_ones_instead(self):
        """A branch with no upstream reports everything unpushed; listing that
        costs more than the rest of the delta."""
        history = GraphHistory()
        build_response(_payload(["a"], version="v1"), None, history, "s")

        new = _payload(["a", "b", "c", "d"], version="v2")
        for commit in new["commits"]:
            commit["pushed"] = False
        new["commits"][3]["pushed"] = True
        response = build_response(new, "v1", history, "s")

        assert response["pushed"] == ["d"]
        assert "unpushed" not in response

    def test_a_delta_still_carries_the_small_fields_whole(self):
        """Branches, head and working changes are cheap; syncing them is not."""
        history = GraphHistory()
        build_response(_payload(["b"], version="v1"), None, history, "s")

        response = build_response(_payload(["a", "b"], version="v2"), "v1", history, "s")

        for field in ("branches", "head", "worktrees", "workingChanges", "mine"):
            assert field in response

    def test_history_is_bounded(self):
        history = GraphHistory(retain=3)
        for n in range(6):
            build_response(_payload(["a"], version=f"v{n}"), None, history, "s")

        assert build_response(_payload(["a"], version="v9"), "v0", history, "s")["reset"] is True
        assert "delta" in build_response(_payload(["a", "z"], version="v9"), "v5", history, "s")

    def test_a_cursor_from_another_session_resets_rather_than_lying(self):
        history = GraphHistory()
        build_response(_payload(["a", "b"], version="v1"), None, history, "session-one")

        response = build_response(_payload(["x", "y"], version="v2"), "v1", history, "session-two")

        assert response["reset"] is True

    def test_a_matching_version_is_trusted_across_sessions(self):
        """Versions are content hashes, so an equal one means equal data."""
        history = GraphHistory()

        response = build_response(_payload(["a"], version="v1"), "v1", history, "any-session")

        assert response == {"version": "v1", "unchanged": True}
