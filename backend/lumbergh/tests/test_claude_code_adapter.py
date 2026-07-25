import asyncio
from pathlib import Path

from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.activity.events import ConversationEvent

FIXTURE = Path(__file__).parent / "fixtures" / "claude_code_sample.jsonl"


def test_conversation_event_defaults_and_dump():
    ev = ConversationEvent(type="agent_message", id="a1", text="hello")
    dumped = ev.model_dump()
    assert dumped["type"] == "agent_message"
    assert dumped["id"] == "a1"
    assert dumped["text"] == "hello"
    assert dumped["tool_name"] is None
    assert dumped["tool_use_id"] is None


def test_conversation_event_represents_opencode_shape():
    # Schema-conformance: the opencode text-part maps onto the same model.
    ev = ConversationEvent(type="agent_message", id="prt_x", text="PONG from jv-desktop")
    assert ev.type == "agent_message"
    tool = ConversationEvent(
        type="tool_call",
        id="prt_y",
        tool_name="bash",
        tool_summary="ls",
        tool_detail='{"command": "ls"}',
        tool_use_id="call_1",
    )
    assert tool.tool_name == "bash"


def test_parse_history_maps_all_block_types():
    adapter = ClaudeCodeAdapter(FIXTURE)
    events = adapter.read_new()
    types = [e.type for e in events]
    assert types == [
        "user_message",
        "thinking",
        "tool_call",
        "tool_result",
        "agent_message",
    ]


def test_tool_call_and_result_share_use_id():
    adapter = ClaudeCodeAdapter(FIXTURE)
    events = adapter.read_new()
    call = next(e for e in events if e.type == "tool_call")
    result = next(e for e in events if e.type == "tool_result")
    assert call.tool_name == "Read"
    assert call.tool_summary == "/repo/app.py"
    assert call.tool_use_id == "toolu_1"
    assert result.tool_use_id == "toolu_1"
    assert result.status == "ok"
    assert "print('hi')" in result.text


def test_read_new_returns_empty_on_second_call_without_appends():
    adapter = ClaudeCodeAdapter(FIXTURE)
    assert len(adapter.read_new()) == 5
    assert adapter.read_new() == []


def test_read_new_only_returns_appended_lines(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"type":"user","message":{"role":"user","content":"first"}}\n')
    adapter = ClaudeCodeAdapter(f)
    assert [e.text for e in adapter.read_new()] == ["first"]

    with f.open("a") as fh:
        fh.write(
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"second"}]}}\n'
        )
    assert [e.text for e in adapter.read_new()] == ["second"]


def test_partial_trailing_line_is_not_consumed_until_newline(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"type":"user","message":{"role":"user","content":"whole"}}\n')
    adapter = ClaudeCodeAdapter(f)
    assert len(adapter.read_new()) == 1

    with f.open("a") as fh:
        fh.write('{"type":"user","message":{"role":"user","content":"partial"')  # no newline yet
    assert adapter.read_new() == []  # incomplete line ignored

    with f.open("a") as fh:
        fh.write("}}\n")  # completes the line
    assert [e.text for e in adapter.read_new()] == ["partial"]


def test_for_cwd_matches_dotted_hidden_dir_encoding(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cwd = Path("/work/proj/.claude/wt/issue-1")
    project_dir = tmp_path / ".claude" / "projects" / "-work-proj--claude-wt-issue-1"
    project_dir.mkdir(parents=True)
    session_file = project_dir / "session.jsonl"
    session_file.write_text('{"type":"user","message":{"role":"user","content":"hi"}}\n')

    adapter = ClaudeCodeAdapter.for_cwd(cwd)

    assert adapter is not None
    assert adapter.path == session_file


def test_for_cwd_returns_none_when_no_project_dir_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude" / "projects").mkdir(parents=True)

    adapter = ClaudeCodeAdapter.for_cwd(Path("/no/such/cwd"))

    assert adapter is None


def test_tail_streams_history_then_stops(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"type":"user","message":{"role":"user","content":"hi"}}\n')
    adapter = ClaudeCodeAdapter(f)

    async def run():
        stop = asyncio.Event()
        collected = []
        async for ev in adapter.tail(stop, poll_interval=0.01):
            collected.append(ev)
            stop.set()  # stop after first event
        return collected

    events = asyncio.run(run())
    assert [e.text for e in events] == ["hi"]
