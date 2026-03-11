"""CLI entry point for Lumbergh."""

import argparse
import shutil
import sys

from lumbergh._version import __version__

REQUIRED_TOOLS = {
    "tmux": "sudo apt install tmux  (or: brew install tmux)",
    "git": "sudo apt install git  (or: brew install git)",
}


def _check_dependencies():
    """Check that required system tools are installed."""
    missing = []
    for cmd, install_hint in REQUIRED_TOOLS.items():
        if shutil.which(cmd) is None:
            missing.append((cmd, install_hint))
    if missing:
        print("Lumbergh requires the following tools:\n", file=sys.stderr)
        for cmd, hint in missing:
            print(f"  {cmd} — install with: {hint}", file=sys.stderr)
        print(file=sys.stderr)
        sys.exit(1)


def run():
    """Run the Lumbergh server."""
    parser = argparse.ArgumentParser(description="Lumbergh - AI Session Supervisor")
    parser.add_argument("--version", action="version", version=f"lumbergh {__version__}")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8420, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    _check_dependencies()

    import uvicorn

    uvicorn.run("lumbergh.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    run()
