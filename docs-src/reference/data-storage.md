# Data Storage

All Lumbergh data lives in a single directory. No database server required.

## Data Directory

Default location: `~/.config/lumbergh/`

Override with the `LUMBERGH_DATA_DIR` environment variable.

## File Layout

```
~/.config/lumbergh/
├── sessions.json              # Session registry (names, workdirs, descriptions)
├── session_data/
│   └── <name>.json            # Per-session data (todos, scratchpad, project prompts)
├── settings.json              # AI provider config, repo search path, git graph commits
├── global.json                # Global prompt templates
└── shared/                    # Shared files accessible from all sessions
```

| File | Contents |
|------|----------|
| `sessions.json` | Session registry -- names, working directories, descriptions |
| `session_data/<name>.json` | Per-session todos, scratchpad notes, and project-specific prompts |
| `settings.json` | AI provider configuration, repo search path, git graph commit count |
| `global.json` | Global prompt templates shared across all sessions |
| `shared/` | Shared files accessible from every session |

## Format

All files are **human-readable JSON** stored via [TinyDB](https://tinydb.readthedocs.io/). You can safely inspect and hand-edit them with any text editor.

!!! warning
    Edit data files only while Lumbergh is stopped, or you risk write conflicts.

## Backup & Restore

Back up everything by copying the data directory:

```bash
cp -r ~/.config/lumbergh/ ~/lumbergh-backup/
```

To restore, copy the backup back to the same path (or point `LUMBERGH_DATA_DIR` at it).
