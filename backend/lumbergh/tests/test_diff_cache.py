"""
Tests for diff_cache fingerprinting.

Regression test for a bug where _git_fingerprint only checked .git metadata
(HEAD, index, refs) and missed unstaged working tree changes, causing the
diff cache to serve stale data.
"""

import time

from lumbergh.diff_cache import _git_fingerprint


class TestGitFingerprint:
    def test_fingerprint_changes_on_commit(self, mock_git_repo_with_changes):
        """Fingerprint should change after staging + committing."""
        import subprocess

        fp1 = _git_fingerprint(mock_git_repo_with_changes)

        subprocess.run(
            ["git", "add", "."],
            cwd=mock_git_repo_with_changes,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test commit"],
            cwd=mock_git_repo_with_changes,
            capture_output=True,
        )

        fp2 = _git_fingerprint(mock_git_repo_with_changes)
        assert fp1 != fp2, "Fingerprint should change after a commit"

    def test_fingerprint_changes_on_unstaged_edit(self, mock_git_repo):
        """Fingerprint should change when a tracked file is modified without staging.

        This is the regression case: editing a file without `git add` should
        still produce a different fingerprint so the diff cache refreshes.
        """
        fp1 = _git_fingerprint(mock_git_repo)

        # Modify a tracked file without staging
        (mock_git_repo / "README.md").write_text("# Modified\n")
        # Ensure mtime granularity doesn't hide the change
        time.sleep(0.05)

        fp2 = _git_fingerprint(mock_git_repo)
        assert fp1 != fp2, (
            "Fingerprint should change when a tracked file is modified (even without git add)"
        )

    def test_fingerprint_changes_on_new_untracked_file(self, mock_git_repo):
        """Fingerprint should change when a new untracked file appears."""
        fp1 = _git_fingerprint(mock_git_repo)

        (mock_git_repo / "new_untracked.txt").write_text("hello\n")

        fp2 = _git_fingerprint(mock_git_repo)
        assert fp1 != fp2, "Fingerprint should change when an untracked file is added"

    def test_fingerprint_stable_when_unchanged(self, mock_git_repo):
        """The worktree status hash (last element) should be stable across calls."""
        # Note: .git/index mtime can shift slightly because `git status`
        # refreshes the stat cache, so we only assert on the status hash.
        fp1 = _git_fingerprint(mock_git_repo)
        fp2 = _git_fingerprint(mock_git_repo)
        assert fp1[-1] == fp2[-1], "Status hash should be stable when nothing changed"
