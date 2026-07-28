import json

from lumbergh.activity.pi import PiAdapter

LINES = [
    {"type": "session", "id": "sid", "timestamp": "2026-07-27T03:48:38.487Z", "cwd": "/w"},
    {
        "type": "message",
        "timestamp": "2026-07-27T03:48:38.545Z",
        "message": {"role": "user", "content": [{"type": "text", "text": "build wordfreq"}]},
    },
    {
        "type": "message",
        "timestamp": "2026-07-27T03:48:40.000Z",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "planning"},
                {"type": "text", "text": "On it."},
                {
                    "type": "toolCall",
                    "id": "call_1",
                    "name": "bash",
                    "arguments": {"command": "uv init"},
                },
            ],
        },
    },
    {
        "type": "message",
        "timestamp": "2026-07-27T03:48:41.000Z",
        "message": {
            "role": "toolResult",
            "toolCallId": "call_1",
            "toolName": "bash",
            "content": [{"type": "text", "text": "done"}],
        },
    },
]


def _write(tmp_path):
    d = tmp_path / "-w--"
    d.mkdir()
    f = d / "2026-07-27T03-48-38_sid.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in LINES) + "\n")
    return f


def test_pi_adapter_parses_events(tmp_path):
    adapter = PiAdapter(_write(tmp_path), root="/w")
    events = adapter.read_new()
    kinds = [(e.type, e.tool_name, (e.text or e.tool_summary)) for e in events]
    assert ("user_message", None, "build wordfreq") in kinds
    assert ("thinking", None, "planning") in kinds
    assert ("agent_message", None, "On it.") in kinds
    assert ("tool_call", "bash", "uv init") in kinds
    tr = [e for e in events if e.type == "tool_result"]
    assert tr
    assert tr[0].tool_use_id == "call_1"
    assert tr[0].text == "done"


def test_for_cwd_encoding(tmp_path, monkeypatch):
    monkeypatch.setattr(PiAdapter, "SESSIONS_DIR", tmp_path)
    d = tmp_path / "--home-jvogel--"
    d.mkdir()
    (d / "a.jsonl").write_text(json.dumps(LINES[0]) + "\n")
    assert PiAdapter.for_cwd("/home/jvogel") is not None
    assert PiAdapter.for_cwd("/nope") is None
