"""Safety guard for the suites under `test/`.

Both E2E suites drive a *real* Lumbergh backend: they create sessions, delete
them, and through `DELETE /api/sessions/{name}` run `tmux kill-session`. tmux is
global per user, and `GET /api/sessions` deliberately lists "orphan tmux sessions
(created outside Lumbergh)" — so a suite pointed at a developer's own machine
enumerates and kills every tmux session that developer has, Lumbergh's own window
included. Once the last session dies the tmux server exits and the desktop goes
with it. That is not hypothetical: it happened twice on 2026-08-22.

Isolating `LUMBERGH_DATA_DIR`, or aiming at a private port, does not help — the
database is isolated but tmux is not. The only safe target is a throwaway machine,
which is what `./test/e2e-vm.sh` builds. It sets the variable below; nothing else
does, so a bare `pytest test/e2e-ui/` now aborts here instead of on your sessions.
"""

import os

import pytest

SANDBOX_ENV = "LUMBERGH_E2E_SANDBOX"


def pytest_configure(config):
    if os.environ.get(SANDBOX_ENV) == "1":
        return
    raise pytest.UsageError(
        f"\n\nRefusing to run the E2E suites: {SANDBOX_ENV} is not set.\n\n"
        "These tests delete every session the target backend reports, which runs\n"
        "`tmux kill-session` on each one. Against a real machine that kills all of\n"
        "your tmux sessions and takes the tmux server down with them.\n\n"
        "Run them the intended way — a disposable QEMU VM:\n\n"
        "    ./test/e2e-vm.sh\n\n"
        f"If you have a throwaway target of your own, set {SANDBOX_ENV}=1 and pass\n"
        "--base-url yourself. Do not set it to point at your own dev server.\n"
    )
