---
title: Dashboard
---

# Dashboard

The dashboard is your home screen -- a bird's-eye view of every AI session you're supervising.

## Session Cards

Sessions are split into two groups:

- **Active** -- sessions with a running tmux session
- **Inactive** -- sessions whose tmux session has been stopped or removed

Each card displays:

| Field | Description |
|-------|-------------|
| **Status** | One of `working`, `waiting`, `idle`, or `error`, auto-detected from terminal output |
| **Current activity** | A short description of what the AI is doing right now |
| **Tmux windows** | Number of windows in the tmux session |
| **Clients** | Whether any WebSocket clients are currently attached |

## Quick Actions

Every card has quick-action buttons:

- **Edit** -- change name, description, or working directory
- **Reset** -- restart the tmux session from scratch
- **Delete** -- remove the session entirely

Click anywhere else on a card to open the full **session detail view**.

## Top Bar

The top-right corner has two controls:

- **Theme toggle** (sun/moon icon) -- switch between dark and light mode. Your preference is saved to `localStorage` and persists across visits.
- **Settings** (gear icon) -- open the settings panel for global configuration.
