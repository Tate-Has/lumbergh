import httpx

import lumbergh.agent_cli.main as cli


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data


def _run(monkeypatch, argv, responder):
    monkeypatch.setattr(cli, "_request", responder)
    monkeypatch.setattr(cli.agent_token, "read_token", lambda: "tok")
    out = []
    monkeypatch.setattr(cli, "_emit", out.append)
    code = cli.main(argv)
    return code, "\n".join(out)


def test_home_lists_sessions(monkeypatch):
    code, out = _run(
        monkeypatch,
        [],
        lambda *_a, **_k: _Resp(
            {"total": 1, "sessions": [{"name": "a", "state": "idle", "unseen": False}]}
        ),
    )
    assert code == 0
    assert "sessions[1]{name,state,unseen}:" in out
    assert "  a,idle,false" in out
    # Header chrome (bin/description/count) is dropped to keep the polled home view lean.
    assert "bin:" not in out
    assert "description:" not in out


def test_unknown_flag_exit_2(monkeypatch):
    code, out = _run(monkeypatch, ["state", "--bogus"], lambda *_a, **_k: _Resp({}))
    assert code == 2
    assert "unknown flag --bogus" in out


def test_babysit_refresh_posts_and_reports(monkeypatch):
    from lumbergh.agent_cli import babysit as babysit_cli

    captured = {}

    def fake_request(method, path, **kwargs):
        captured.update(method=method, path=path, json=kwargs.get("json"))
        return _Resp({"session": "port", "refreshed": True})

    out = []
    monkeypatch.setattr(babysit_cli, "_request", fake_request)
    monkeypatch.setattr(babysit_cli, "_emit", out.append)
    rc = babysit_cli.run({"--refresh": True, "--session": "port"})

    assert rc == 0
    assert (captured["method"], captured["path"], captured["json"]) == (
        "POST",
        "/api/bill/babysit/refresh",
        {"session": "port"},
    )
    assert "refreshed" in "\n".join(out)


def test_babysit_refresh_reports_a_refusal(monkeypatch):
    from lumbergh.agent_cli import babysit as babysit_cli

    def fake_request(*_a, **_k):
        return _Resp(
            {"detail": {"error": "port is not being babysat", "help": "start it first"}}, status=400
        )

    errs = []
    monkeypatch.setattr(babysit_cli, "_request", fake_request)
    monkeypatch.setattr(babysit_cli, "_err", lambda msg, _help, code: errs.append(msg) or code)
    rc = babysit_cli.run({"--refresh": True, "--session": "port"})

    assert rc == 1
    assert "not being babysat" in errs[0]


def test_server_down_exit_1(monkeypatch):
    def boom(*_a, **_k):
        raise httpx.ConnectError("refused")

    code, out = _run(monkeypatch, [], boom)
    assert code == 1
    assert "server is not running" in out


def test_wait_timeout_exit_1(monkeypatch):
    code, out = _run(
        monkeypatch,
        ["wait", "--session", "s", "--until", "idle"],
        lambda *_a, **_k: _Resp(
            {"session": "s", "state": "working", "waited": 300, "reached": False}
        ),
    )
    assert code == 1
    assert "timed out" in out


def test_wait_output_requires_match_or_regex(monkeypatch):
    code, out = _run(monkeypatch, ["wait-output", "--session", "s"], lambda *_a, **_k: _Resp({}))
    assert code == 2
    assert "--match or --regex is required" in out


def test_wait_output_success(monkeypatch):
    code, out = _run(
        monkeypatch,
        ["wait-output", "--session", "s", "--match", "DONE"],
        lambda *_a, **_k: _Resp({"session": "s", "matched": True, "waited": 0.0}),
    )
    assert code == 0
    assert "matched" in out


def test_wait_output_timeout_exit_1(monkeypatch):
    code, out = _run(
        monkeypatch,
        ["wait-output", "--session", "s", "--match", "DONE", "--timeout", "5"],
        lambda *_a, **_k: _Resp({"session": "s", "matched": False, "waited": 5.0}),
    )
    assert code == 1
    assert "timed out" in out
