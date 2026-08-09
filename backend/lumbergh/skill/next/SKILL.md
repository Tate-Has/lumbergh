---
name: next
description: >
  Take the next item off this repo's Lumbergh backlog, do it, commit it locally, and tick
  it off — the one-task-at-a-time loop a babysat session runs after each `/clear`. Use when
  you are asked to work the backlog, pick up the next todo, or continue where the last
  cycle left off. Do NOT use to push, open PRs, or spawn other sessions.
---

# next — work one item off the backlog

You are a session Lumbergh is babysitting. Your context was just cleared, so the backlog —
not your memory — is the state that survived. Take one item, do it, record that you did,
and stop. Something else decides whether the loop runs again.

## 1. Ask what is next

```
lb todo next
```

**Exit code 1 means the backlog is empty.** Print exactly this line and nothing after it,
then stop:

```
⟳ BACKLOG-EMPTY
```

Otherwise it prints the item's `index`, `text` and `description`. Keep the index — you
need it in step 3.

## 2. Do the work

Work that one item, and only that item. Follow the repo's own conventions: read its
`CLAUDE.md` / `AGENTS.md` and do what they say about tests, lint, and style. Run the
project's own validation gate before you call the work done.

When you are finished, **commit locally**.

**Never push, never open a PR, never touch a remote.** Progress stays reviewable on this
machine; the user decides what leaves it. This is the whole guardrail on an unattended
loop, so do not talk yourself out of it because the change is small or the branch is
yours.

Do not spawn workers or worktrees. This loop is one session doing one thing at a time.

## 3. Record what happened

```
lb todo done <index>
```

Tick it off only when it is genuinely finished. If you ran out of road partway — blocked,
out of context, the item turned out to be bigger than it read — leave it undone and append
one line to the project scratchpad saying where you got to, so the next cycle starts from
there instead of from scratch.

## 4. Hand back

Print exactly this line, on its own, with nothing after it:

```
⟳ REFRESH-READY
```

That sentinel is what tells the babysit loop this cycle is over.
