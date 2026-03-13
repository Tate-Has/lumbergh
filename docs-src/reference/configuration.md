# Configuration

## Settings UI

Click the **gear icon** in the dashboard top-right corner to open settings.

### General

| Setting | Description | Default |
|---------|-------------|---------|
| Repository search directory | Root path Lumbergh scans to find git repos when creating sessions | `~/src` |
| Git graph commits | Number of commits shown in the graph visualization (10--1000) | `100` |

### AI

See the [AI Providers](../guides/ai-providers.md) guide for details on configuring AI backends.

## CLI Arguments

```bash
lumbergh [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--host`, `-H` | Bind address | `0.0.0.0` |
| `--port`, `-p` | Port number | `8420` |
| `--reload` | Enable auto-reload (development only) | off |

**Example:**

```bash
# Start on a custom port, bind to localhost only
lumbergh -H 127.0.0.1 -p 9000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LUMBERGH_DATA_DIR` | Override the data directory | `~/.config/lumbergh/` |

```bash
# Store data in a custom location
LUMBERGH_DATA_DIR=/data/lumbergh lumbergh
```

## Theme

Toggle between **dark** and **light** mode using the button in the top-right corner of the dashboard. Your preference is persisted to `localStorage` and restored on next visit.
