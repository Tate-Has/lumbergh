# Lumbergh

A self-hosted web dashboard for supervising multiple Claude Code AI sessions running in tmux.

Think "micromanager for your AI interns."

## Features

- **Multi-session dashboard** — view and manage multiple Claude Code sessions at a glance
- **Terminal streaming** — interact with live terminal sessions via xterm.js + WebSockets
- **Git diff viewer** — monitor live diffs, commit history, and branch switching as the AI works
- **Git graph** — visualize commit history with an interactive graph
- **File browser** — browse project files with syntax highlighting
- **AI chat** — manager AI agent for reviewing and coordinating work
- **Todo lists & scratchpad** — per-project notes and task tracking
- **Prompt templates** — reusable prompts with mention/variable support
- **Shared files** — share context across sessions
- **Settings** — configurable AI providers and preferences
- **Mobile-friendly** — responsive design for phones and tablets
- **PWA support** — installable as a progressive web app

## Quick Start

```bash
# Install frontend dependencies (first time only)
cd frontend && npm install && cd ..

# Start both backend and frontend
./start.sh
```

Backend runs on `:8000`, frontend on `:5173`.

Or run separately:
```bash
./backend/start.sh   # Backend on :8000
./frontend/start.sh  # Frontend on :5173
```

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, libtmux, TinyDB
- **Frontend:** React + Vite + TypeScript, xterm.js, TanStack Query, Tailwind CSS

## Project Structure

```
lumbergh/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── tmux_pty.py           # PTY/tmux attachment logic
│   ├── session_manager.py    # PTY pooling for WebSocket clients
│   ├── git_utils.py          # Git operations (diff, log, branches)
│   ├── file_utils.py         # File browsing utilities
│   ├── db_utils.py           # TinyDB persistence helpers
│   ├── diff_cache.py         # Diff caching layer
│   ├── idle_detector.py      # Session idle detection
│   ├── idle_monitor.py       # Idle monitoring service
│   ├── message_buffer.py     # Message buffering for AI context
│   ├── models.py             # Pydantic models
│   ├── constants.py          # Shared constants
│   ├── ai/                   # AI provider integration
│   │   ├── providers.py
│   │   └── prompts.py
│   ├── routers/
│   │   ├── ai.py             # AI chat endpoints
│   │   ├── notes.py          # Todo, scratchpad, prompt template APIs
│   │   ├── sessions.py       # Session management endpoints
│   │   ├── settings.py       # Settings endpoints
│   │   └── shared.py         # Shared files endpoints
│   ├── tests/
│   ├── pyproject.toml
│   └── start.sh
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   └── SessionDetail.tsx
│   │   ├── components/
│   │   │   ├── Terminal.tsx
│   │   │   ├── QuickInput.tsx
│   │   │   ├── DiffViewer.tsx
│   │   │   ├── FileBrowser.tsx
│   │   │   ├── TodoList.tsx
│   │   │   ├── Scratchpad.tsx
│   │   │   ├── PromptTemplates.tsx
│   │   │   ├── SessionCard.tsx
│   │   │   ├── CreateSessionModal.tsx
│   │   │   ├── BranchPicker.tsx
│   │   │   ├── SettingsModal.tsx
│   │   │   ├── SharedFiles.tsx
│   │   │   ├── ResizablePanes.tsx
│   │   │   ├── VerticalResizablePanes.tsx
│   │   │   ├── diff/
│   │   │   │   ├── FileList.tsx
│   │   │   │   ├── FileDiff.tsx
│   │   │   │   └── CommitList.tsx
│   │   │   └── graph/
│   │   ├── hooks/
│   │   └── utils/
│   └── start.sh
├── slides/                # Slidev presentation
├── docs/                  # PRD, architecture, roadmap
├── start.sh               # Start both backend + frontend
└── LICENSE
```

## License

MIT
