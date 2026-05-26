# Fork Upgrade Triage → upstream v0.18.1

This document triages the 33 commits unique to Tate's Lumbergh fork against upstream `voglster/lumbergh@v0.18.1`. The user has decided to **branch fresh from v0.18.1 and cherry-pick / re-implement keepers** rather than rebase, because upstream v0.18.0 (`c483219`) was a sweeping design-system rewrite that re-skinned essentially every frontend component using new `components/ui/` primitives (GlassPanel, Button, Badge, Banner, Modal, StatusDot, Tabs, Input) and Tailwind v4 `@theme` tokens. As a result, almost every fork commit that touches `Dashboard.tsx`, `SessionDetail.tsx`, `TerminalHeader.tsx`, `TabBar.tsx`, `SessionCard*.tsx`, `Scratchpad.tsx`, or `FileBrowser.tsx` will need to be **manually reimplemented** as a behavior spec on top of the new components — not cherry-picked as a patch.

## Triage Table

| SHA | Subject | Area | Recommendation | Rationale |
|---|---|---|---|---|
| `ccbb7e8` | feat(terminal): add collapse button for side tool pane | frontend | **manual-reimplement** | Touches `SessionDetail.tsx` which upstream v0.18.0 rewrote against the new design system. Small (16 lines) — re-add as a button on new layout. |
| `327f7c6` | fix(idle): overhaul session-state detection for modern Claude Code | backend | **cherry-pick (clean)** | Backend-only (`idle_detector.py`, `idle_monitor.py`, tests) plus a one-line `useSessionStatus.ts` tweak. Should apply cleanly; supersedes `faeee5c` and `fafbc62`. |
| `edbe2a0` | fix(terminal): keep selections stable and add Ctrl+C-to-copy | frontend/terminal | **manual-reimplement** | `Terminal.tsx` was modified by upstream v0.18.0 design system. Logic is small, reapply onto new file. |
| `33d8e25` | feat(shortcuts): rebind session cycling to Ctrl+Shift+J/K | frontend | **manual-reimplement** | Touches `Terminal.tsx` + `SessionDetail.tsx` (both rewritten upstream) plus docs. Behavior is trivial; replay onto new files. |
| `c32641c` | fix(terminal): omit cols/rows from XTerm options when no cached size | frontend/terminal | **manual-reimplement** | 3-line fix in upstream-rewritten `Terminal.tsx`. Re-add in init path. |
| `366a2d2` | chore(terminal): suppress complexity lint on init useEffect | chore | **drop (chore/superseded)** | One-line eslint-disable — only meaningful if the original useEffect survives, which it won't after reimplementing terminal fixes. |
| `f65a815` | merge: integrate upstream terminal/session fixes and pop-out feature | merge | **drop (merge commit)** | Pure merge — its contents come from upstream and prior fork commits already in this list. |
| `81ddbcc` | fix(scratchpad): cancel stale fetch on session change | frontend | **drop (superseded)** | **Confirmed identical fix** in upstream `3118044`. Diffs differ only in comments/whitespace; upstream version is already in v0.18.1. |
| `1db6ea9` | fix(sessions): show cleanup screen when worktree is gone | backend+frontend | **cherry-pick (risky)** | Backend `sessions.py` change is clean; frontend `SessionDetail.tsx` + `SessionCard.tsx` (both rewritten upstream) need reimplementation. Split the commit. |
| `3120dc0` | feat(file-browser): native CSV/TSV table viewer | frontend | **drop (superseded)** | Upstream `83f7719` is the exact same feature (`CsvViewer.tsx` is the same 208 lines — Tate's PR was merged upstream). Already in v0.18.1. |
| `ae782a8` | fix(file-browser): resizable sidebar + consistent icons | frontend | **manual-reimplement** | `FileBrowser.tsx` was redesigned in v0.18.0. Reapply the icon-consistency + resize-handle behavior on the new component. |
| `6c7f88a` | fix(terminal): treat Ctrl+V as paste for clipboard injection tools | frontend/terminal | **manual-reimplement** | Small (33 lines) in upstream-rewritten `Terminal.tsx`. Important UX fix — keep as a spec. |
| `ca473f1` | fix(frontend): iOS safe-area on TabBar | frontend | **manual-reimplement** | `TabBar.tsx` was substantially reworked upstream; replay the `env(safe-area-inset-*)` adjustments on the new file. Also touches `index.html` (likely clean). |
| `52af0a3` | fix(terminal): clear xterm buffer before writing initial pane snapshot | frontend+backend | **cherry-pick (risky)** | Backend `session_manager.py` change should apply; `Terminal.tsx` + `useTerminalSocket.ts` lines need reapplication on upstream-rewritten files. |
| `ecd5ce1` | fix(idle_monitor): add missing `re` import (Windows) | backend | **cherry-pick (clean)** | One-line import fix; subsumed if `327f7c6` already covers it — verify and drop if so. |
| `6c6e1aa` | merge: integrate upstream v0.15.0 | merge | **drop (merge commit)** | Pure merge; contents already upstream. |
| `a1f0435` | feat(nav): Sessions/Workspace toggle, replace back arrow | frontend | **manual-reimplement** | Adds new `ViewToggle.tsx` + edits `TabBar.tsx`, `TerminalHeader.tsx`, `SessionDetail.tsx` — all rewritten upstream. Decide whether this nav model still makes sense given new UI. |
| `7852f32` | fix(paste): Route multiline pastes through tmux paste-buffer | frontend+backend | **cherry-pick (risky)** | `tmux_pty.py` one-liner is clean; `Terminal.tsx` 31-line bracketed-paste handler needs replay on upstream-rewritten file. High-value fix. |
| `e67c409` | Merge branch 'main' into feat/focus-workspace | merge | **drop (merge commit)** | Merge. |
| `984f0bc` | Merge remote-tracking branch 'origin/main' | merge | **drop (merge commit)** | Merge. |
| `f0a1129` | fix(layout): Wrap routes in flex column | frontend | **decide-later** | Touches `App.tsx` which upstream v0.18.0 rewrote. Whether this is still needed depends on Focus-workspace decision and new App.tsx height cascade. |
| `209189b` | fix(focus): Exclude waiting tasks from in-flight panel | focus | **decide-later** | One-line tweak inside Focus workspace — only valid if Focus is being carried forward. |
| `32076a3` | feat(focus): Pomodoro duration picker + fix pause icon | focus | **decide-later** | Focus-workspace only. |
| `f016051` | fix: Back button returns to last view, not previous session | frontend | **decide-later** | Tied to Focus/Workspace nav model. `App.tsx` and `SessionDetail.tsx` rewritten upstream. |
| `95be1d8` | feat(focus): Session picker + unified card design | focus | **decide-later** | Focus-only; substantial. |
| `43a9e0e` | refactor: Extract AppHeader, simplify Dashboard/Focus topbars | frontend | **decide-later** | Adds `AppHeader.tsx`; upstream v0.18.0 has its own header concept (GlassPanel/Tabs primitives). Likely obsolete. |
| `c16db62` | fix(focus): Sliding view toggle + workspace theme cascade | focus | **decide-later** | `TabBar.tsx` rewritten upstream; theme tokens now live in `@theme` blocks. Replay only if Focus stays. |
| `1965131` | feat: Merge Focus Workspace into Lumbergh as /focus page | focus | **decide-later** | **Major feature (~30 new files).** Backend adds `routers/focus.py`, `focus_export.py`, `models.py` — these are clean. Frontend adds 25+ Focus components that pre-date the v0.18.0 design system. **Need user input: keep Focus?** If yes, the backend half cherry-picks cleanly; the frontend half needs a design-system pass. |
| `cc6195b` | Merge branch 'feat/session-hibernate' | merge | **drop (merge commit)** | Squashed into `d500fc3` content already. |
| `faeee5c` | fix(idle): Score-based detection system | backend | **drop (superseded)** | Superseded by later fork commit `327f7c6` "overhaul session-state detection." |
| `a0d4c6b` | chore: Remove stale peer dependency markers | chore | **drop (chore/superseded)** | `package-lock.json` housekeeping; regenerate on the v0.18.1 base instead. |
| `d500fc3` | feat(sessions): Add session hibernation | backend+frontend | **cherry-pick (risky)** | Backend `sessions.py` (~97 lines, new endpoint) should apply; frontend `Dashboard.tsx` + `SessionCardActions.tsx` need reimplementation on new design system. **High-value feature.** |
| `fafbc62` | fix(idle): Detect subagent activity, longer stall threshold | backend | **drop (superseded)** | Superseded by `327f7c6` overhaul. |

---

## Keeper Clusters

### 1. Idle detection overhaul (S–M)
- **Commits:** `327f7c6` (+ verify `ecd5ce1` Windows `re` import isn't already inside it)
- **Effort:** S — backend-only, has tests.
- **Dependencies:** none.
- **Notes:** Drops `faeee5c` and `fafbc62` as superseded. Sanity-check that the one-line `useSessionStatus.ts` change still fits the upstream hook.

### 2. Terminal UX hardening (M)
- **Commits:** `edbe2a0` (Ctrl+C-to-copy + stable selections), `c32641c` (cols/rows guard), `33d8e25` (Ctrl+Shift+J/K cycling), `6c7f88a` (Ctrl+V paste), `7852f32` (multiline paste via tmux buffer), `52af0a3` (clear buffer before snapshot), `ccbb7e8` (collapse tool pane button).
- **Effort:** M — each fix is small but `Terminal.tsx` was rewritten upstream, so they all need to be replayed against the new component. Roughly a half-day of careful re-application + manual testing.
- **Dependencies:** none beyond upstream `Terminal.tsx`.
- **Open question:** Does upstream v0.18.0 already include any of these fixes natively? Worth a quick read of the new `Terminal.tsx` before starting.

### 3. Session lifecycle (M)
- **Commits:** `d500fc3` (hibernation — backend endpoint + dashboard button), `1db6ea9` (worktree-gone cleanup screen).
- **Effort:** M — backend halves are clean cherry-picks; frontend halves need design-system reimplementation on `Dashboard.tsx` / `SessionCard.tsx` / `SessionDetail.tsx`.
- **Dependencies:** none.
- **Open question:** Is hibernation still relevant with the upstream `2359ba9` PTY env fix? Probably yes — they solve different problems.

### 4. Mobile / safe-area polish (S)
- **Commits:** `ca473f1` (iOS safe-area on TabBar).
- **Effort:** S — needs to be reapplied to the new `TabBar.tsx`.
- **Dependencies:** none.

### 5. Focus Workspace (L — gated on user decision)
- **Commits:** `1965131` (initial merge), `c16db62`, `43a9e0e`, `95be1d8`, `f016051`, `32076a3`, `209189b`, `a1f0435`, `f0a1129`.
- **Effort:** L — ~30 new files, none built on the new design system. Backend half (`routers/focus.py`, `focus_export.py`, `models.py`, `db_utils.py` additions) is clean. Frontend half is significant rework.
- **Dependencies:** All other keepers can land first; Focus is independent.
- **Open question:** **This is the biggest decision.** Is Focus still wanted? If yes, do you want to use v0.18.0 design primitives throughout, or keep the existing Focus look and just bridge nav?

---

## Open Questions

1. **Focus Workspace — keep it?** It's nearly half the fork-only commits and the only thing requiring a "L" effort estimate. If it's experimental, dropping the whole cluster could shrink the upgrade to a 1-2 day exercise.
2. **Hibernation feature direction** — keep `d500fc3` as-is, or rework after upstream's new design system gives better affordances (e.g., a Modal confirmation)?
3. **Nav model (`a1f0435` Sessions/Workspace toggle)** — only relevant if Focus stays. If Focus is dropped, this commit drops with it.
4. **`327f7c6` vs upstream idle code** — upstream may have its own idle improvements between merge-base `d8aae6e` and v0.18.1; worth diffing `idle_detector.py` against the v0.18.1 version before cherry-picking, even though the file isn't in the v0.18.0 changed-files list.
5. **`AppHeader.tsx` (`43a9e0e`)** — upstream v0.18.0 introduced its own header pattern via GlassPanel + Tabs primitives. Likely the fork's AppHeader is obsolete and should be dropped, with any unique behavior re-expressed inside upstream's pattern.
