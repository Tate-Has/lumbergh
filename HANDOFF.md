# HANDOFF — generic backlog loop for Bill

Implementing `docs/superpowers/specs/2026-08-09-bill-generic-backlog-loop-design.md`.
**Read that spec first** — it carries the why. This file carries the how: decisions already
made, exact landing sites, and the order to build in. Delete this file when the work lands.

## State

Design approved. Nothing implemented yet. Four pieces, each useful on its own, in this order.

---

## 1. `/api/bill/todos` — repo-scoped todo access

**Why it doesn't exist yet:** the current endpoints (`routers/sessions.py:1856`,
`/{name}/todos`) resolve a project *through a session*. The CLI has only a repo path.

**Land in:** `backend/lumbergh/routers/bill.py` (router prefix is `/api/bill`, see line 36;
`POST /init` at line 1088 is the pattern to copy — it takes a repo path in the body).

**Storage is unchanged.** Both views hit the same project DB:
`get_project_db(workdir).table("todos")`, read/written with
`get_single_document_items` / `save_single_document_items` from `db_utils`.
Item shape is `models.TodoItem`: `{text: str, done: bool, description: str | None}`.

**Endpoints:**

| Route | Body / query | Returns |
|---|---|---|
| `GET /api/bill/todos` | `?repo=<path>` | `{"todos": [...]}` |
| `POST /api/bill/todos/done` | `{repo, index}` | the updated item |
| `POST /api/bill/todos/add` | `{repo, text, description?}` | the created item |

**Decision — mutations happen server-side, not read-modify-write in the CLI.** A CLI that
GETs the list, edits it and POSTs it back races other writers. The server is the only writer,
and `db_utils` now serializes access per file (see `_SerializedTable`), so doing the mutation
in the endpoint makes it atomic.

**Decision — `index` is 1-based over the *whole* list**, done items included, so what
`lb todo` prints and what `done <n>` accepts are the same numbers. Out of range → 400 with a
message naming the valid range.

## 2. `lb todo` — the CLI

**Land in:** new `backend/lumbergh/agent_cli/todo.py`, registered in
`agent_cli/main.py` alongside the others. `agent_cli/init.py` is the closest template: it
takes `--repo`, posts to `/api/bill/...` via `_request`, renders with `toon`, and returns
`_err(...)` on failure.

```
lb todo                    # list: index, done, text
lb todo next               # first undone item
lb todo done <n>           # tick it off
lb todo add <text>         # append
```

- `--repo` defaults to cwd (`lb init` requires it; **for todo, default it** — the babysat
  session is already sitting in the repo).
- Output via `toon.render_collection` for the list, `toon.render_object` for `next`.
- **`lb todo next` is the load-bearing one.** It must print the **index** as well as the text
  and description, because the skill feeds that index straight back to `lb todo done`. With
  nothing undone it prints nothing and **exits 1**, so the skill can branch on exit code
  rather than parsing.

## 3. The `next` skill

**Land in:** `backend/lumbergh/agent_cli/skill.py` — add to the `SKILLS` table beside
`lb`/`ship`/`scout`, and commit the matching copy at `backend/lumbergh/skill/next/SKILL.md`.
`lb skill --check` guards the two against drift, so **they must match byte for byte**.

It rides the existing `ensure_worker_skills()` auto-install (called from `routers/bill.py:869`
before a worker boots), which is what makes this work with no setup.

**Skill body:**

1. `lb todo next` — exit 1? Print `⟳ BACKLOG-EMPTY` on its own line, nothing after it, stop.
2. Otherwise work it, following the repo's own `CLAUDE.md` / `AGENTS.md`.
3. Commit locally. **Never push, never open a PR, never touch a remote.**
4. `lb todo done <index>`. If the task ended mid-flight, append one line to the project
   scratchpad saying where it got to.
5. Print `⟳ REFRESH-READY` on its own line.

The todo list *is* the handoff — ticking items off is the state that survives `/clear`.

**Decision — the skill is named `next`**, matching the short unprefixed convention of
`lb`/`ship`/`scout`. It is generic enough to collide with a user's own skill; that risk is
accepted. If a collision shows up in the wild, rename to `lb-next` rather than prefixing
everything.

## 4. Defaults, template, docs

- `backend/lumbergh/babysit.py` `DEFAULTS`: `"on_refresh": ["/clear", "/next"]`
  (was `["/clear", "/fleet-start"]`). Update the docstring on `read_config`, which currently
  says the defaults match the port convention.
- **Add `~/src/personal/port/.lumbergh.toml`** with `[babysit] on_refresh = ["/clear",
  "/fleet-start"]` so port keeps its fleet behaviour. **Do this in the same change** — port is
  actively babysat and would otherwise silently switch loops.
- `backend/lumbergh/bill/AGENTS.md.template`: add a short paragraph saying a repo with todos
  can be babysat with no setup, and what the loop does. Every `/fleet-*` mention there today is
  a prohibition, so nothing tells Bill the generic path exists.
- User-facing docs: a `[babysit]` configuration section. It is currently documented only
  inside a design spec, which is why the escape hatch may as well not exist.

---

## Guardrail, stated honestly

The loop may **work and commit locally; it may not push**. This is skill *instruction*, not a
mechanical gate — the same soft guarantee `ship` relies on. Do not describe it as sandboxed. A
mechanical gate is a separate change and out of scope.

## Testing

Red-green per `CLAUDE.md`: failing test first, watch it fail, then fix.

- `lb todo`: list, next, done, add; repo defaulting; **exit 1 on an empty backlog**;
  index out of range.
- `/api/bill/todos`: repo scoping, atomic done, add.
- The changed `babysit.py` default.
- Skill drift is already covered by `lb skill --check` — make sure it passes.

`cd backend && uv run pytest` · `cd frontend && npx vitest run` · `./lint.sh` from the root.
Lint must be clean before finishing; it enforces complexity limits that have bitten twice in
this codebase (extract a helper rather than suppress).

## Gotchas

- **`lb skill --check` fails loudly** if the string in `skill.py` and the committed
  `SKILL.md` diverge. Edit both.
- The backend runs under `uvicorn --reload` in the `lumbergh:2` tmux window — edits go live
  immediately, no restart needed. Do not start a second server.
- Commit messages: no `Co-Authored-By`, no AI attribution.
- Pushing `main` triggers CI and publishes an alpha. Ask before pushing.

## Out of scope

Spawning parallel workers (the loop is sequential by design), porting port's fleet skills into
Lumbergh, and a mechanical push gate. See the spec's *Out of scope*.
