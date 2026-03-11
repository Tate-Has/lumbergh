"""File browser endpoint tests."""


def test_list_session_files(client, test_session, test_repo_dir):
    r = client.get(f"/api/sessions/{test_session}/files")
    assert r.status_code == 200
    data = r.json()
    assert "files" in data
    assert "root" in data
    assert data["root"] == test_repo_dir
    # Should at least contain README.md from our git init
    file_paths = [f["path"] if isinstance(f, dict) else f for f in data["files"]]
    assert any("README" in str(f) for f in file_paths)


def test_get_file_content(client, test_session):
    r = client.get(f"/api/sessions/{test_session}/files/README.md")
    assert r.status_code == 200
    data = r.json()
    assert "content" in data
    assert "language" in data


def test_get_missing_file_returns_404(client, test_session):
    r = client.get(f"/api/sessions/{test_session}/files/nonexistent.xyz")
    assert r.status_code == 404
