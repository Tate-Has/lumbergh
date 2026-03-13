---
title: Shared Files
---

# Shared Files

The **Shared** tab in the session detail right pane gives every session access to a common set of files. Use it to share context, instructions, or reference material across projects.

## Storage

Shared files live in:

```
~/.config/lumbergh/shared/
```

## Adding Files

There are two ways to add shared files:

- **Upload** -- use the upload button in the Shared tab
- **Manual** -- drop files directly into the `~/.config/lumbergh/shared/` directory

## Use Cases

!!! example "Common shared files"
    - **CLAUDE.md instructions** -- keep a master set of coding conventions available to every session
    - **Reference docs** -- API specs, style guides, architecture notes
    - **Cross-project context** -- share decisions or findings from one project with others

Shared files are available to all sessions immediately -- no restart required.
