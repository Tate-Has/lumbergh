import subprocess
from pathlib import Path
from unittest.mock import patch

from lumbergh.routers.sessions import create_tmux_session


def test_injects_lumbergh_session_env(tmp_path: Path):
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("lumbergh.routers.sessions.subprocess.run", side_effect=fake_run):
        create_tmux_session("mysess", tmp_path, launch_command="claude")

    send_keys = [c for c in calls if "send-keys" in c]
    exports = [c for c in send_keys if any("export LUMBERGH_SESSION=" in str(a) for a in c)]
    assert exports, f"no export keystroke found in {send_keys}"
    assert any("mysess" in str(a) for a in exports[0])
    launch_idx = next(i for i, c in enumerate(calls) if any("claude" in str(a) for a in c))
    export_idx = next(
        i for i, c in enumerate(calls) if any("export LUMBERGH_SESSION=" in str(a) for a in c)
    )
    assert export_idx < launch_idx
