import lumbergh.agent_token as at


def test_ensure_creates_token_0600(tmp_path, monkeypatch):
    path = tmp_path / "agent-token"
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", path)
    tok = at.ensure_token()
    assert tok
    assert path.exists()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert at.ensure_token() == tok  # stable across calls


def test_read_and_verify(tmp_path, monkeypatch):
    path = tmp_path / "agent-token"
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", path)
    tok = at.ensure_token()
    assert at.read_token() == tok
    assert at.verify(tok) is True
    assert at.verify("nope") is False
    assert at.verify(None) is False


def test_verify_no_token_file(tmp_path, monkeypatch):
    monkeypatch.setattr(at, "AGENT_TOKEN_FILE", tmp_path / "absent")
    assert at.verify("anything") is False
    assert at.read_token() is None
