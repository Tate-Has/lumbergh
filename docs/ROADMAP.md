# Lumbergh Feature Roadmap

## Where We Are

Lumbergh is a **full supervision cockpit** for Claude Code sessions — terminal streaming, live diffs, git graph, file browser, todos, prompt templates, multi-session dashboard, mobile PWA, idle detection, AI status summaries, session pause/cycling. Phases 1–4 are complete.

It's running on Tailscale for friends and colleagues. Real users means real requirements: auth, stability, and polish matter now. The competitive landscape (claude-squad, agent-view, agtx) remains shallow — nobody else combines terminal + live diffs + todos + prompts + mobile in one tool.

**Strategic direction:** Personal polish → Open-source community → Revenue/SaaS.

---

## Phase 5: Auth & Security

**Why:** Real people are on the Tailscale network. A password-less dashboard that controls terminal sessions is a liability.

- Simple password gate (single shared password, not multi-user accounts)
- Protect all HTTP endpoints and WebSocket connections
- Cookie/token-based session so you don't re-enter on every page load
- Environment variable or config file for the password
- No user management, no OAuth, no roles — just a lock on the front door

---

## Phase 6: Manager AI (Code Reviewer)

**Why:** The Manager AI starts as a **reactive code reviewer**, not an autonomous PM. It answers questions about what sessions are doing and reviews their work.

- Chat endpoint with streaming responses
- Auto-inject session context: recent terminal output, git diff, file tree
- Multi-turn conversation history stored per-session
- Frontend chat pane with markdown rendering
- Quick prompts: "review the last commit", "what did this session just do?", "write a PR description"
- Select a diff hunk → ask the manager about it

The manager watches and comments. It doesn't drive sessions or make autonomous decisions.

---

## Phase 7: Power User Polish

**Why:** The daily-driver experience needs to feel fast and complete before going public.

- **Notifications & alerts** — PWA push notifications for "needs input" / "errored" / "idle too long". Leverage existing idle_detector states.
- **Session orchestration** — task queue with dependencies, auto-assign to sessions, visual board showing what's running where
- **Command palette** — Cmd+K to jump to any session, file, todo, prompt. Keyboard-driven workflow.
- **Keyboard shortcuts** — navigate sessions, switch tabs, trigger actions without touching the mouse
- **Global search** — search across files, todos, scratchpads, prompts, terminal scrollback
- **Terminal recording & playback** — capture session output, timeline scrubbing, "what happened while I was gone?" AI summary
- **Session analytics** — commits/hour, lines changed, time-to-idle, productivity trends

---

## Phase 8: Community & Sharing

**Why:** Open-source growth requires making Lumbergh easy to adopt, configure, and contribute to.

- Prompt template export/import/sync — share prompt packs as JSON
- CLAUDE.md template editor — AI-assisted "generate a CLAUDE.md from this repo"
- Plugin/hook system — user-defined hooks ("on idle, run tests"), plugin API for custom widgets
- Docker image — one-command deployment
- ~~Onboarding flow — first-run wizard, example sessions, getting-started guide~~ ✓ shipped
- GitHub presence — issue templates, contributing guide, release automation

---

## Phase 9: Monetization (Open Core)

**Why:** Sustainability. The core stays free and self-hosted forever.

- **Free tier:** Everything self-hosted — terminal, diffs, todos, prompts, manager AI (BYO API key)
- **Paid cloud sync:** Prompt library sync, session history across machines, shared team workspaces
- **Team features:** Multi-user auth, role-based access, shared dashboards, audit logs
- **Explore hosted option:** Managed Lumbergh instance (no tmux setup required) — only if demand justifies it

---

## What We Cut

- **Cross-tool session handoff** — interesting but niche. Lumbergh is for Claude Code, not a universal adapter.
- **Merge conflict resolution UI** — git handles this fine. Not worth the complexity.
- **SSH multi-machine support** — Tailscale already solves remote access. Adding SSH transport is a whole new failure mode.
- **Side-by-side diff with inline comments** — unified diff works. Comments belong in the manager AI chat, not the diff view.

---

## Build Order

1. **Auth** — non-negotiable with real users on the network
2. **Manager AI** — completes the core vision, code reviewer first
3. **Notifications** — people need to walk away and get pinged

Everything else is sequenced by user demand.

---

## Anti-Patterns to Avoid

- Don't try to replace the terminal — Lumbergh supervises, it doesn't drive
- Don't build a full IDE — file browser and diffs are for monitoring, not editing
- Don't over-invest in AI autonomy before the reviewer model is solid — reactive first, proactive later
- Don't add complexity for hypothetical scale — single-user password gate before multi-tenant auth
- Don't over-invest in AI chat before notifications — people need alerts before they need a conversation
