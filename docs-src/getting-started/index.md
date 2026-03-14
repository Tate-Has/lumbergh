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

!!! info "What's uv?"
    [uv](https://docs.astral.sh/uv/) is a fast Python package manager from [Astral](https://astral.sh/). `uv tool install` installs CLI tools into isolated environments so they don't conflict with other Python packages on your system. If you don't have it yet:

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    See the [uv docs](https://docs.astral.sh/uv/getting-started/installation/) for other install methods (Homebrew, pip, Windows, etc).

!!! tip "Alternative: pip"
    If you'd rather not use uv, pip works too:

    ```bash
    pip install pylumbergh
    ```

!!! note "Prerequisites"
    Lumbergh requires Python 3.11+, tmux, and git. See [Prerequisites](prerequisites.md) for full details.

## First Run

When you run `lumbergh` for the first time, it will:

1. Start the web dashboard on port 8420
2. Show a **welcome screen** that pre-fills your repo search directory to the folder you launched from
3. Let you confirm the directory and create your first session right away

!!! tip "Launch from your projects folder"
    Run `lumbergh` from the directory that contains your git repos (e.g. `~/src`) so it auto-detects the right search path.

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
