---
title: Prompt Templates
---

# Prompt Templates

Prompt templates are reusable prompts you can fire at any session with a single click. Find them in the **Prompts** tab of the session detail right pane.

## Scopes

Templates exist at two levels:

| Scope | Visibility | Storage |
|-------|-----------|---------|
| **Project** | Only the current session/project | `~/.config/lumbergh/projects/{hash}.json` |
| **Global** | All sessions | `~/.config/lumbergh/global.json` |

!!! tip "Promote to global"
    Any project template can be promoted to global with one click -- handy when you write a prompt you want everywhere.

## Using Templates

Click a template to send it directly to the active terminal session. The prompt is typed into the terminal exactly as written.

## Edit Mode

Toggle edit mode to manage your templates:

- **Reorder** -- drag and drop to change the order
- **Move** -- shift templates between project and global scope
- **Delete** -- remove templates you no longer need

## Persistence

Templates persist across restarts. Project templates are stored in the per-project JSON file, and global templates live in `global.json`. No data is lost when you stop and restart Lumbergh.
