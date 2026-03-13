---
title: Prerequisites
---

# Prerequisites

Lumbergh has a small set of dependencies. Most are likely already on your system.

## Required

### Python 3.11+

The backend runs on Python 3.11 or newer.

```bash
python3 --version
```

### tmux

Terminal session management is built on tmux.

=== "Ubuntu/Debian"

    ```bash
    sudo apt install tmux
    ```

=== "macOS"

    ```bash
    brew install tmux
    ```

### git

Used for the diff viewer and worktree management. Usually pre-installed on most systems.

```bash
git --version
```

## Installation Tool

### uv (recommended)

The fastest way to install Lumbergh.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

!!! tip "Alternative: pip"
    You can also install with `pip` if you prefer. Any Python package manager that supports PyPI packages will work.

## Development Only

### Node.js 18+

Only required if you're working on Lumbergh itself. Not needed for normal usage.

```bash
node --version
```
