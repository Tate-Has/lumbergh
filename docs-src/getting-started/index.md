---
title: Installation
---

# Installation

Get Lumbergh running in under a minute.

## Quick Start

```bash
uv tool install pylumbergh
lumbergh
```

Open [http://localhost:8420](http://localhost:8420) in your browser. That's it.

!!! tip "Alternative: pip"
    If you don't use `uv`, install with pip instead:

    ```bash
    pip install pylumbergh
    ```

!!! note "Prerequisites"
    Lumbergh requires Python 3.11+, tmux, and git. See [Prerequisites](prerequisites.md) for full details.

## First Run

When you run `lumbergh` for the first time, it will:

1. Create a tmux session for managing Claude Code terminals
2. Start the web dashboard on port 8420
3. Open the UI where you can add and supervise AI sessions

## CLI Options

```bash
lumbergh                          # Start with defaults
lumbergh --host 0.0.0.0          # Bind to all interfaces (default)
lumbergh --port 8420             # Set the port (default: 8420)
lumbergh --reload                # Auto-reload on code changes (dev only)
```

## WSL

Lumbergh works great under WSL. If you haven't set up WSL yet:

```bash
wsl --install
```

Ports forward automatically from WSL to Windows, so you can access the dashboard from your Windows browser at `http://localhost:8420` with no extra configuration.
