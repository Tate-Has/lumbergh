import json

from lumbergh.hook_installer import desired_command, ensure_installed, uninstall

MARKER = "lumbergh_session_start.py"


def _settings(tmp_path):
    return tmp_path / "settings.json"


def _managed_groups(path):
    hooks = json.loads(path.read_text()).get("hooks", {}).get("SessionStart", [])
    return [g for g in hooks if any(MARKER in h.get("command", "") for h in g.get("hooks", []))]


def test_fresh_install_creates_managed_entry(tmp_path):
    sp = _settings(tmp_path)
    assert ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER) is True
    groups = _managed_groups(sp)
    assert len(groups) == 1
    assert groups[0]["hooks"][0]["type"] == "command"


def test_idempotent_rerun_is_byte_identical(tmp_path):
    sp = _settings(tmp_path)
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    first = sp.read_text()
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    assert sp.read_text() == first
    assert len(_managed_groups(sp)) == 1


def test_preserves_unrelated_hooks(tmp_path):
    sp = _settings(tmp_path)
    sp.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": "~/x.sh"}]}
                    ]
                }
            }
        )
    )
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    data = json.loads(sp.read_text())
    assert data["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
    assert len(_managed_groups(sp)) == 1


def test_stale_interpreter_is_rewritten(tmp_path):
    sp = _settings(tmp_path)
    ensure_installed(settings_path=sp, interpreter="/old/py", script=tmp_path / MARKER)
    ensure_installed(settings_path=sp, interpreter="/new/py", script=tmp_path / MARKER)
    groups = _managed_groups(sp)
    assert len(groups) == 1
    assert groups[0]["hooks"][0]["command"] == desired_command("/new/py", tmp_path / MARKER)


def test_malformed_settings_left_untouched(tmp_path):
    sp = _settings(tmp_path)
    sp.write_text("{ this is not json")
    assert ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER) is False
    assert sp.read_text() == "{ this is not json"


def test_uninstall_removes_only_managed(tmp_path):
    sp = _settings(tmp_path)
    sp.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": "/other/hook.py"}]}]
                }
            }
        )
    )
    ensure_installed(settings_path=sp, interpreter="/py", script=tmp_path / MARKER)
    assert uninstall(settings_path=sp) is True
    hooks = json.loads(sp.read_text())["hooks"]["SessionStart"]
    assert len(hooks) == 1
    assert hooks[0]["hooks"][0]["command"] == "/other/hook.py"
