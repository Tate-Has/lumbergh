"""E2E roundtrip for the worktree lifecycle: create -> ls -> reap.

Uses the shared, VM-provisioned ``test-repo`` (via the ``test_repo_dir``
fixture) as the worktree parent rather than a host-side scratch repo. The
client only ever sends path strings — all git/filesystem work happens
server-side — so a server-visible provisioned path works whether the test
runs against a local dev server or under ``test/e2e-vm.sh``, where pytest
runs on the host but the server (and ``test-repo``) live inside the VM.
The test only ever adds/removes its own uniquely-named branch and worktree;
it never touches ``test-repo``'s tracked content, so it's safe to share with
other E2E tests.
"""

import uuid
from pathlib import Path


def test_worktree_create_list_reap_roundtrip(client, test_repo_dir):
    branch = f"e2e/worktree-{uuid.uuid4().hex[:8]}"
    created_path = None
    try:
        r = client.post(
            "/api/worktrees",
            json={"repo": test_repo_dir, "branch": branch, "create_branch": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "path" in body, body
        wt_path = body["path"]
        created_path = wt_path

        listed = client.get("/api/worktrees", params={"repo": test_repo_dir}).json()["worktrees"]
        entry = next((w for w in listed if Path(w["path"]) == Path(wt_path).resolve()), None)
        assert entry is not None, f"Created worktree not in listing: {listed}"
        assert entry["state"] == "orphan"  # no live session attached in this test

        reaped = client.post(
            "/api/worktrees/reap",
            json={"path": wt_path, "force": True, "rm_branch": True},
        )
        assert reaped.status_code == 200, reaped.text
        assert reaped.json()["status"] == "removed"
        created_path = None

        listed_after = client.get("/api/worktrees", params={"repo": test_repo_dir}).json()[
            "worktrees"
        ]
        assert not any(Path(w["path"]) == Path(wt_path).resolve() for w in listed_after), (
            f"Reaped worktree still listed: {listed_after}"
        )
    finally:
        if created_path:
            client.post(
                "/api/worktrees/reap",
                json={"path": created_path, "force": True, "rm_branch": True},
            )
