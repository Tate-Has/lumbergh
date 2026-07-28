import lumbergh.hook_installer as hook_installer


def test_ensure_installed_survives_exceptions(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("no home")

    monkeypatch.setattr(hook_installer, "ensure_installed", boom)
    from lumbergh.main import install_session_hook

    install_session_hook()  # must not raise
