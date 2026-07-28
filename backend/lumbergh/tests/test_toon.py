from lumbergh.agent_cli.toon import render_block, render_collection, render_object


def test_collection():
    out = render_collection("sessions", [{"name": "a", "state": "idle"}], ["name", "state"])
    assert out.splitlines()[0] == "sessions[1]{name,state}:"
    assert out.splitlines()[1] == "  a,idle"


def test_collection_quotes_when_needed():
    out = render_collection("x", [{"t": "hi, there"}], ["t"])
    assert out.splitlines()[1] == '  "hi, there"'


def test_empty_collection():
    assert render_collection("x", [], ["a"]) == "x[0]{a}:"


def test_object():
    assert render_object([("state", "blocked"), ("since", 12)]) == "state: blocked\nsince: 12"


def test_block():
    out = render_block("pane", "l1\nl2")
    assert out == "pane: |\n  l1\n  l2"
