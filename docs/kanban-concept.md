# Kanban Board — Concept

Exploratory notes on adding a Kanban board to Lumbergh, inspired by Claude Cowork's Productivity plugin which turns local task files into a live Kanban board showing AI workload.

## Option A: Todo View Toggle (Simplest)

A List/Board toggle inside the existing Todo tab. Same data, different visualization.

- Add optional `column` field to existing todos: `"backlog" | "in_progress" | "done"`
- Backward-compatible: todos without `column` derive it from `done` flag
- Board view shows 3 columns with drag-drop between them
- Moving to "Done" column sets `done=true`, moving out sets `done=false`
- Display-only hint: when session is "working", top undone task gets a visual glow/badge
- List view (current TodoList) continues to work unchanged

**Scope**: ~1-2 days. Mostly frontend (new KanbanBoard component), tiny backend model change.

**Pros**: Minimal complexity, no new endpoints needed, leverages existing todo CRUD
**Cons**: Per-project scope only, doesn't add cross-session planning capability

## Option B: Planning Board with Session Dispatch (More Ambitious)

A higher-level planning board where you organize work, then dispatch tasks to sessions.

- New "Board" concept at the global or multi-project level
- Cards represent work items (features, bugs, tasks) — richer than todos
- Columns: Backlog / Assigned / In Progress / Done
- "Assign to session" action pulls a card into that session's todo list
- Session idle state auto-updates the card's visual status (working/idle/error indicators)
- Dashboard-level view showing all cards across projects
- Lightweight project management layer on top of the todo system

**Scope**: ~1-2 weeks. New backend entity, new API, new UI components, cross-session aggregation.

**Pros**: Genuine planning/dispatch capability, cross-session visibility, aligns with Phase 7 "session orchestration" roadmap item
**Cons**: Significant complexity, risk of over-engineering, overlaps with Phase 7 task queue

## Recommendation

Option A fits naturally as Phase 7 polish — low-cost view toggle. Option B is really the "session orchestration" feature (task queue with dependencies, auto-assign to sessions, visual board). If pursued, scope it as its own phase after Manager AI (Phase 6).

## References

- [Claude Cowork Productivity Plugin](https://claudecowork.im/blog/productivity-plugin-tutorial) — local Kanban from markdown files
- [Anthropic Cowork Plugins](https://www.reworked.co/collaboration-productivity/anthropic-adds-plugins-to-claude-cowork/)
