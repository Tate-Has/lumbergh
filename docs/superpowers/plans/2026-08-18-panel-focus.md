# Panel Focus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Any pane can fill the desktop viewport — the terminal via Alt+Z as today, and now the right panel via a maximize button — with Files finally getting a resizable tree.

**Architecture:** `useZenMode`'s boolean becomes `useFocusMode`'s `'none' | 'main' | 'panel'`, with the decision logic extracted as a pure function. `ResizablePanes` grows a `collapse` direction replacing its boolean, and collapsing the *left* pane hides it without unmounting, because that side holds a live PTY and WebSocket. `FileBrowser` swaps its fixed sidebar for a nested `ResizablePanes`.

**Tech Stack:** React 19 + TypeScript, Vite, Tailwind, vitest + jsdom + @testing-library/react, Playwright + pytest-bdd.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-18-panel-focus-design.md`. Read it before starting.
- Collapsing the LEFT pane must never unmount it. It holds the terminal — a live PTY, a WebSocket, and scrollback. This regression has been fixed twice in this codebase and is guarded by a socket-count assertion.
- Collapsing the RIGHT pane leaves it unrendered, exactly as today. Panel state is re-fetchable; this is deliberate asymmetry, not an oversight.
- `Alt+Z` always targets the MAIN pane. It must never land the user in panel focus.
- `localStorage` key exactly `lumbergh:focusMode`, values `'none'` / `'main'` / `'panel'`. Migration: when that key is absent and `lumbergh:zenMode === 'true'`, read as `'main'`.
- "Terminal Only" wins over panel focus. A stored `'panel'` has no effect while it is on, and focus is NOT rewritten — turning it off restores what you had.
- Desktop only. Mobile must not change.
- Chords match on `e.code`, never `e.key` — on macOS Option+Z reports `e.key === 'Ω'`.
- Backend untouched. No Python changes outside `test/e2e-ui/`.
- Run `./lint.sh` from the repo root before every commit.
- Dev servers (vite :5420, backend :8420) run in a user-managed tmux window — never start, restart, or kill them. As of `21e8c69` they are supervised and self-restart, which does NOT mean you may kill them.
- `backend/lumbergh/frontend_dist/` is a gitignored prebuilt bundle `:8420` serves in preference to `frontend/dist`, AND the PWA service worker shadows it again. Rebuild, resync via `build.sh`'s copy step, clear the service worker, and confirm the loaded `/assets/index-*.js` hash changed before trusting any browser observation.

---

### Task 1: The focus state machine

Replace the zen boolean with a three-state focus target. The decision logic goes in `utils/` as a pure function so it can be tested directly, matching how `conversationFollow.ts` was extracted.

**Files:**
- Create: `frontend/src/utils/focusMode.ts`
- Create: `frontend/src/utils/focusMode.test.ts`
- Create: `frontend/src/hooks/useFocusMode.ts`
- Delete: `frontend/src/hooks/useZenMode.ts`

**Interfaces:**
- Consumes: `useIsDesktop` from `../hooks/useMediaQuery`.
- Produces: from `utils/focusMode.ts` — `type FocusTarget = 'none' | 'main' | 'panel'`, `readStoredFocus(focusRaw: string | null, zenRaw: string | null): FocusTarget`, `nextMainFocus(current: FocusTarget): FocusTarget`, `nextPanelFocus(current: FocusTarget): FocusTarget`. From `hooks/useFocusMode.ts` — `useFocusMode(): { focus: FocusTarget; setFocus: (f: FocusTarget) => void; toggleMain: () => void; togglePanel: () => void }`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/utils/focusMode.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { readStoredFocus, nextMainFocus, nextPanelFocus } from './focusMode'

describe('readStoredFocus', () => {
  it('reads a stored focus value', () => {
    expect(readStoredFocus('panel', null)).toBe('panel')
    expect(readStoredFocus('main', null)).toBe('main')
    expect(readStoredFocus('none', null)).toBe('none')
  })

  it('migrates a zen user with no focus key', () => {
    expect(readStoredFocus(null, 'true')).toBe('main')
    expect(readStoredFocus(null, 'false')).toBe('none')
  })

  it('prefers the focus key over the legacy zen key', () => {
    expect(readStoredFocus('panel', 'true')).toBe('panel')
  })

  it('treats anything unrecognized as none', () => {
    expect(readStoredFocus('sideways', null)).toBe('none')
    expect(readStoredFocus(null, null)).toBe('none')
  })
})

describe('nextMainFocus', () => {
  it('toggles main on and off', () => {
    expect(nextMainFocus('none')).toBe('main')
    expect(nextMainFocus('main')).toBe('none')
  })

  it('takes over from panel focus rather than clearing it', () => {
    expect(nextMainFocus('panel')).toBe('main')
  })
})

describe('nextPanelFocus', () => {
  it('toggles panel on and off', () => {
    expect(nextPanelFocus('none')).toBe('panel')
    expect(nextPanelFocus('panel')).toBe('none')
  })

  it('takes over from main focus', () => {
    expect(nextPanelFocus('main')).toBe('panel')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/utils/focusMode.test.ts
```

Expected: FAIL — `Failed to resolve import "./focusMode"`.

- [ ] **Step 3: Write the pure module**

Create `frontend/src/utils/focusMode.ts`:

```ts
/** Which pane, if any, fills the viewport.
 *
 * Alt+Z always targets 'main', so the chord can never strand the user in panel
 * focus — the panel is only reachable through its own maximize button. */
export type FocusTarget = 'none' | 'main' | 'panel'

const VALID: FocusTarget[] = ['none', 'main', 'panel']

/** `zenRaw` is the pre-focus `lumbergh:zenMode` value. Anyone already in zen
 * keeps their setting rather than silently losing it on upgrade. */
export function readStoredFocus(focusRaw: string | null, zenRaw: string | null): FocusTarget {
  if (focusRaw && (VALID as string[]).includes(focusRaw)) return focusRaw as FocusTarget
  if (focusRaw === null && zenRaw === 'true') return 'main'
  return 'none'
}

export function nextMainFocus(current: FocusTarget): FocusTarget {
  return current === 'main' ? 'none' : 'main'
}

export function nextPanelFocus(current: FocusTarget): FocusTarget {
  return current === 'panel' ? 'none' : 'panel'
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/utils/focusMode.test.ts
```

Expected: PASS, all cases.

- [ ] **Step 5: Write the hook**

Create `frontend/src/hooks/useFocusMode.ts`. Read `frontend/src/hooks/useZenMode.ts` first — this replaces it and should keep its shape and its comments where they still apply:

```ts
import { useCallback, useEffect, useState } from 'react'
import { useIsDesktop } from './useMediaQuery'
import { type FocusTarget, nextMainFocus, nextPanelFocus, readStoredFocus } from '../utils/focusMode'

const STORAGE_KEY = 'lumbergh:focusMode'
const LEGACY_ZEN_KEY = 'lumbergh:zenMode'

/** Focus mode: one pane fills the desktop viewport, with the other pane and the
 * page banners not rendered. Alt+Z toggles the main pane in both directions —
 * Esc is deliberately not an exit key, because the terminal needs it.
 *
 * State lives in localStorage rather than server settings: it is a per-browser
 * view preference, like the ResizablePanes widths, and toggling must be
 * instant. */
export function useFocusMode() {
  const isDesktop = useIsDesktop()
  const [focus, setFocusState] = useState<FocusTarget>(() =>
    readStoredFocus(localStorage.getItem(STORAGE_KEY), localStorage.getItem(LEGACY_ZEN_KEY))
  )

  const setFocus = useCallback((next: FocusTarget) => {
    setFocusState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }, [])

  const toggleMain = useCallback(() => setFocus(nextMainFocus(focus)), [focus, setFocus])
  const togglePanel = useCallback(() => setFocus(nextPanelFocus(focus)), [focus, setFocus])

  useEffect(() => {
    if (!isDesktop) return

    const onKeyDown = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      // Physical key position, not e.key: on macOS Option+Z reports e.key === 'Ω',
      // which would make this chord dead. Trade-off: on Dvorak/AZERTY the key
      // labelled Z isn't the one that toggles.
      if (e.code !== 'KeyZ') return
      e.preventDefault()
      setFocus(nextMainFocus(focus))
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isDesktop, focus, setFocus])

  // The stored preference survives a narrow viewport; only the rendered value is
  // gated, so widening the window restores what the user had.
  return { focus: isDesktop ? focus : ('none' as FocusTarget), setFocus, toggleMain, togglePanel }
}
```

- [ ] **Step 6: Delete the old hook and confirm nothing references it**

```bash
cd frontend && rm src/hooks/useZenMode.ts
grep -rn "useZenMode" src/ || echo "no references"
```

`SessionDetail.tsx` still imports it at this point, so the grep WILL show that one reference. Leave it — Task 4 rewires it, and the typecheck will fail until then. Do not partially wire SessionDetail here.

- [ ] **Step 7: Commit**

The typecheck cannot pass until Task 4 rewires the consumer, so run only the unit suite here.

```bash
cd frontend && npx vitest run src/utils/focusMode.test.ts
./lint.sh || true
git add frontend/src/utils/focusMode.ts frontend/src/utils/focusMode.test.ts frontend/src/hooks/useFocusMode.ts frontend/src/hooks/useZenMode.ts
git commit -m "feat(focus): three-state focus target replacing the zen boolean"
```

If `./lint.sh` fails only on the known `useZenMode` import in `SessionDetail.tsx`, that is expected — commit anyway and note it in your report. Any OTHER lint failure must be fixed before committing.

---

### Task 2: ResizablePanes gains a collapse direction

The boolean becomes a direction. Collapsing left must hide without unmounting; collapsing right keeps today's unrendered behavior.

**Files:**
- Modify: `frontend/src/components/ResizablePanes.tsx`
- Create: `frontend/src/components/resizablePanes.test.tsx`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `ResizablePanes` prop `collapse?: 'left' | 'right' | null` (default `null`), replacing `collapsed?: boolean`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/resizablePanes.test.tsx`. The repo already has jsdom and `@testing-library/react` as dev dependencies, and `vitest.config.ts` already collects `.tsx` tests:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import ResizablePanes from './ResizablePanes'

const panes = (collapse: 'left' | 'right' | null) => (
  <ResizablePanes
    collapse={collapse}
    left={<div data-testid="left-child">left</div>}
    right={<div data-testid="right-child">right</div>}
  />
)

describe('ResizablePanes collapse', () => {
  it('renders both panes when nothing is collapsed', () => {
    const { queryByTestId } = render(panes(null))
    expect(queryByTestId('left-child')).not.toBeNull()
    expect(queryByTestId('right-child')).not.toBeNull()
  })

  it('drops the right pane from the DOM when collapsing right', () => {
    const { queryByTestId } = render(panes('right'))
    expect(queryByTestId('left-child')).not.toBeNull()
    expect(queryByTestId('right-child')).toBeNull()
  })

  it('keeps the left pane MOUNTED but hidden when collapsing left', () => {
    // The left pane holds the terminal: a live PTY, a WebSocket and scrollback.
    // Unmounting it reconnects the session, so it must stay in the DOM.
    const { queryByTestId } = render(panes('left'))
    expect(queryByTestId('right-child')).not.toBeNull()
    const leftChild = queryByTestId('left-child')
    expect(leftChild).not.toBeNull()
    expect(leftChild!.closest('[data-pane="left"]')).toHaveProperty('style.display', 'none')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/components/resizablePanes.test.tsx
```

Expected: FAIL — `collapse` is not a prop yet, so the collapsing cases render both panes normally.

- [ ] **Step 3: Implement the direction**

In `frontend/src/components/ResizablePanes.tsx`, replace `collapsed?: boolean` in the props interface with:

```ts
  // Which pane, if either, gives up its width. Collapsing 'left' HIDES it rather
  // than unrendering it: that side holds the terminal, and unmounting tears down
  // xterm and its WebSocket. Collapsing 'right' unrenders, since panel state is
  // cheap to rebuild.
  collapse?: 'left' | 'right' | null
```

Destructure it as `collapse = null` in place of `collapsed = false`, and change the render to:

```tsx
  return (
    <div ref={containerRef} className="flex h-full">
      {/* Left pane */}
      <div
        data-pane="left"
        style={
          collapse === 'left'
            ? { display: 'none' }
            : { width: collapse === 'right' ? '100%' : `${leftWidth}%` }
        }
        className="h-full overflow-hidden"
      >
        {left}
      </div>

      {!collapse && (
        {/* Splitter — unchanged, keep the existing element exactly as it is */}
      )}

      {collapse !== 'right' && (
        <div
          style={{ width: collapse === 'left' ? '100%' : `${100 - leftWidth}%` }}
          className="h-full overflow-hidden"
        >
          {right}
        </div>
      )}
    </div>
  )
```

Keep the splitter element itself byte-identical, including its handlers and classes — only its surrounding condition changes from `!collapsed` to `!collapse`. Do not touch `leftWidth`, its persistence effect, or any drag handler: the stored width must survive a collapse round-trip in either direction untouched.

- [ ] **Step 4: Update the existing call site**

`frontend/src/pages/SessionDetail.tsx` currently passes `collapsed={isZen || isTerminalOnly}`. Change it to `collapse={isZen || isTerminalOnly ? 'right' : null}` so behavior is identical. Task 4 rewrites this expression properly; this step only keeps the tree compiling.

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/components/resizablePanes.test.tsx
```

Expected: PASS, 3 tests.

- [ ] **Step 6: Commit**

```bash
cd frontend && npx vitest run
cd /home/jvogel/src/personal/lumbergh && ./lint.sh || true
git add -A frontend/src
git commit -m "feat(panes): collapse by direction, keeping the left pane mounted"
```

The known `useZenMode` import failure from Task 1 may still be present; any other failure must be fixed first.

---

### Task 3: Failing UI test for panel focus

Feature-first red-green. Committed failing; Task 4 turns it green.

**Files:**
- Create: `test/e2e-ui/features/panel_focus.feature`
- Create: `test/e2e-ui/test_panel_focus.py`

**Interfaces:**
- Consumes: shared steps in `test/e2e-ui/conftest.py` — `Given a test session exists`, `Given I am on the session page for "{name}"`. Existing test ids `terminal-container`, `file-preview`, `tab-files`.
- Produces: the `data-testid="panel-maximize"` contract Task 4 must satisfy.

- [ ] **Step 1: Write the feature file**

Create `test/e2e-ui/features/panel_focus.feature`:

```gherkin
Feature: Panel focus
  As a user I want the right panel to fill the viewport so I can work in
  Files without the terminal taking half the screen.

  Scenario: Maximizing the panel gives Files the whole viewport
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    When I click the "files" tab
    And I click the panel maximize button
    Then I should see the file preview
    And the terminal container is present but hidden

  Scenario: The terminal survives a trip through panel focus
    Given a test session exists
    And I record terminal websocket connections
    And I am on the session page for "e2e-ui-session"
    When I click the panel maximize button
    And I click the panel maximize button
    Then the terminal websocket connected exactly once
```

- [ ] **Step 2: Write the step definitions**

Create `test/e2e-ui/test_panel_focus.py`. pytest-bdd does not resolve steps across test modules, so every step not in `conftest.py` is defined here. The websocket recorder is copied from `test_session_view.py:16-31` rather than imported, for the same reason:

```python
"""Panel focus step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/panel_focus.feature")

TERMINAL_WS_PATH = "/stream"


@given("I record terminal websocket connections", target_fixture="terminal_ws_connections")
def record_terminal_ws_connections(page: Page) -> list[str]:
    """Arm the recorder BEFORE navigation.

    The terminal socket opens as soon as the component mounts, so a listener
    attached afterwards sees nothing and the assertion passes vacuously.
    """
    seen: list[str] = []

    def record(ws) -> None:
        if TERMINAL_WS_PATH in ws.url:
            seen.append(ws.url)

    page.on("websocket", record)
    return seen


@when(parsers.parse('I click the "{tab}" tab'))
def click_tab(page: Page, tab: str):
    page.locator(f'[data-testid="tab-{tab}"]').click()


@when("I click the panel maximize button")
def click_panel_maximize(page: Page):
    page.locator('[data-testid="panel-maximize"]').click()


@then("I should see the file preview")
def see_file_preview(page: Page):
    expect(page.locator('[data-testid="file-preview"]')).to_be_visible(timeout=10000)


@then("the terminal container is present but hidden")
def terminal_present_but_hidden(page: Page):
    # Present AND hidden, not merely invisible: unmounting the terminal would
    # tear down xterm and its WebSocket, which is the regression being guarded.
    locator = page.locator('[data-testid="terminal-container"]')
    expect(locator).to_have_count(1, timeout=10000)
    expect(locator).not_to_be_visible(timeout=10000)


@then("the terminal websocket connected exactly once")
def terminal_ws_connected_once(terminal_ws_connections: list[str]):
    assert len(terminal_ws_connections) == 1, (
        f"expected exactly 1 terminal websocket, saw {len(terminal_ws_connections)}: "
        f"{terminal_ws_connections}"
    )
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd test/e2e-ui && .venv/bin/python -m pytest test_panel_focus.py -v --base-url http://localhost:8420 --repo-dir "$HOME"
```

Expected: both scenarios FAIL at `I click the panel maximize button` — no element carries `data-testid="panel-maximize"` yet.

If the run errors on fixtures, a missing venv, or step-matching instead, that is a broken test rather than a red one. Fix the invocation and re-run until the only failure is the missing button.

- [ ] **Step 4: Commit the failing test**

```bash
cd /home/jvogel/src/personal/lumbergh
git add test/e2e-ui/features/panel_focus.feature test/e2e-ui/test_panel_focus.py
git commit -m "test(focus): failing UI test for panel maximize"
```

---

### Task 4: Wire panel focus into the page

Turns Task 3 green.

**Files:**
- Modify: `frontend/src/pages/SessionDetail.tsx`
- Modify: `frontend/src/pages/TerminalWindow.tsx` (if it imports the removed hook)

**Interfaces:**
- Consumes: `useFocusMode` from Task 1, `collapse` from Task 2.
- Produces: `data-testid="panel-maximize"` on the tab bar button, required by Task 3.

- [ ] **Step 1: Swap the hook**

In `frontend/src/pages/SessionDetail.tsx`, replace the `useZenMode` import and its call:

```ts
import { useFocusMode } from '../hooks/useFocusMode'
// ...
const { focus, setFocus, togglePanel } = useFocusMode()
```

Then replace every remaining `isZen` reference with `focus === 'main'`, and `exitZen` with `() => setFocus('none')`. There are references at the `ScratchPromoteBanner` gate (~line 724), the `collapse` prop, the `ZenTerminal active` prop, the `Tabs` button condition, and `collapseHeader` on `Terminal` (~line 499).

Then check `frontend/src/pages/TerminalWindow.tsx` for a `useZenMode` import and give it the same treatment if present.

- [ ] **Step 2: Compute the collapse direction**

Replace the `collapse` expression on `ResizablePanes` with:

```tsx
collapse={
  focus === 'main' || isTerminalOnly ? 'right' : focus === 'panel' ? 'left' : null
}
```

`isTerminalOnly` deliberately takes precedence over `focus === 'panel'`: it is an explicit saved per-session setting, while focus is a transient view preference. A stored `'panel'` simply has no effect while Terminal Only is on, and focus is NOT rewritten, so turning the setting off restores what the user had.

- [ ] **Step 3: Hide the banner in either focus**

Change the banner gate from `{!isZen && (` to `{focus === 'none' && (` — a focused pane means a focused pane, whichever one it is.

- [ ] **Step 4: Add the maximize button**

In `renderRightPanel()`, inside the panel switcher row (the `flex gap-1 p-2 bg-bg-surface border-b border-border-default` div, ~line 568), add this immediately BEFORE the gear icon's wrapping `<div className="relative ml-auto" ...>`, and change that gear wrapper's class from `relative ml-auto` to `relative` so the maximize button carries the `ml-auto` push instead:

```tsx
<button
  onClick={togglePanel}
  data-testid="panel-maximize"
  className="ml-auto px-2 py-1 rounded text-text-tertiary hover:text-text-secondary hover:bg-control-bg-hover transition-colors"
  title={focus === 'panel' ? 'Restore split view' : 'Maximize panel'}
>
  {focus === 'panel' ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
</button>
```

Import `Maximize2` and `Minimize2` from `lucide-react` alongside the existing icon imports.

The tab bar stays visible while the panel is focused, so tabs remain switchable without leaving full screen.

- [ ] **Step 5: Typecheck and unit tests**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
```

Expected: clean. This is the first point where the typecheck can pass, since Task 1 deleted a hook `SessionDetail` was still importing.

- [ ] **Step 6: Run the UI test to verify it now passes**

Rebuild and resync `backend/lumbergh/frontend_dist` via `build.sh`'s copy step, clear the service worker, and confirm the loaded `/assets/index-*.js` hash changed. Then:

```bash
cd test/e2e-ui && .venv/bin/python -m pytest test_panel_focus.py test_session_view.py test_zen.py test_terminal.py -v --base-url http://localhost:8420 --repo-dir "$HOME"
```

Expected: all passing. Never edit a test to make it pass; if you believe a test is wrong, stop and report NEEDS_CONTEXT.

- [ ] **Step 7: Verify Alt+Z and Terminal Only by hand**

In the browser: press Alt+Z from panel focus and confirm it goes to main focus rather than to `'none'`. Turn Terminal Only on via the gear menu while panel focus is stored, confirm the terminal fills the pane, then turn it off and confirm panel focus returns. Report what you observed.

- [ ] **Step 8: Commit**

```bash
cd /home/jvogel/src/personal/lumbergh && ./lint.sh
git add -A frontend
git commit -m "feat(focus): maximize the right panel from the tab bar"
```

---

### Task 5: Files gets a resizable tree

The last piece of the user's actual request: a file explorer you can drag wider.

**Files:**
- Modify: `frontend/src/components/FileBrowser.tsx`

**Interfaces:**
- Consumes: `collapse` from Task 2.
- Produces: nothing.

- [ ] **Step 1: Replace the fixed sidebar with nested panes**

In `frontend/src/components/FileBrowser.tsx`, the render currently opens `<div className="h-full flex">` and conditionally renders a `w-64 flex-shrink-0` sidebar (~line 687) followed by the content viewer (~line 710).

Replace that structure with a `ResizablePanes`, keeping the tree markup and the content-viewer markup exactly as they are — only their container changes:

```tsx
<ResizablePanes
  collapse={sidebarCollapsed ? 'left' : null}
  storageKey="lumbergh:filesTreeWidth"
  defaultLeftWidth={25}
  minLeftWidth={10}
  maxLeftWidth={50}
  left={/* the existing sidebar div, minus its w-64 flex-shrink-0 classes */}
  right={/* the existing file content viewer div, unchanged */}
/>
```

Import `ResizablePanes from './ResizablePanes'`. Drop `w-64 flex-shrink-0` from the sidebar since the pane now owns its width, and keep `border-r border-border-default overflow-auto`.

The existing collapse button keeps its `setSidebarCollapsed(true)` handler — it now routes through `collapse` rather than through a conditional render, so the tree keeps its scroll position across a collapse round-trip.

The floating "send selection to terminal" button at the end of the component is a sibling of this structure — leave it exactly where it is in the tree.

- [ ] **Step 2: Typecheck and unit tests**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
```

Expected: clean.

- [ ] **Step 3: Verify the tree resizes**

Rebuild, resync `frontend_dist`, clear the service worker, confirm the bundle hash changed. Then in the browser: open Files, maximize the panel, drag the splitter between tree and preview, and confirm the tree widens and the preview shrinks. Reload and confirm the width persisted. Collapse the tree with its button and confirm the preview takes the full width, then restore it.

- [ ] **Step 4: Verify the selection button, which is the thing most likely to be wrong**

`FileBrowser` renders its "send selection to terminal" button with `position: fixed` and hand-computed coordinates (`buttonPos`). Panel focus and the resizable tree both move the layout underneath it.

Select text inside a file preview while the panel is maximized, and confirm the button appears NEXT TO the selection — not merely that it appears somewhere. Repeat in the normal split view. Report the observed position in both, with a screenshot. Screenshots go to `/tmp/claude-1000/-home-jvogel-src-personal-lumbergh/158319eb-d53d-4e99-a45c-73ae70bbeb9b/scratchpad/` — chrome-devtools-axi screenshots silently fail to write under the repo tree.

If it is misplaced, fix the coordinate computation. Do not delete the button.

- [ ] **Step 5: Run the full UI suite**

```bash
cd test/e2e-ui && .venv/bin/python -m pytest test_panel_focus.py test_session_view.py test_zen.py test_terminal.py test_file.py -v --base-url http://localhost:8420 --repo-dir "$HOME"
```

Expected: all passing. `test_file.py` is included because this task changes the Files layout it exercises.

- [ ] **Step 6: Commit**

```bash
cd /home/jvogel/src/personal/lumbergh && ./lint.sh
git add -A frontend
git commit -m "feat(files): resizable file tree"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Three focus states | 1 |
| Alt+Z always targets main, never strands in panel | 1 (`nextMainFocus`, tested) |
| Panel reachable only via its own button | 4 |
| Tab bar stays visible while panel focused | 4 (button lives in that bar) |
| Sticky per browser under `lumbergh:focusMode` | 1 |
| Zen migration from `lumbergh:zenMode` | 1 (`readStoredFocus`, tested) |
| Desktop only, mobile unchanged | 1 (`isDesktop` gate) |
| `collapse: 'left' \| 'right' \| null` | 2 |
| Left collapse keeps the pane mounted | 2 (unit test), 3 (socket-count guard) |
| Right collapse unrenders, as today | 2 (unit test) |
| Persisted width survives a collapse round-trip | 2 step 3 (drag/persistence untouched), 5 step 3 |
| `ZenTerminal` wired to `focus === 'main'` | 4 step 1 |
| Terminal-only wins over panel focus, focus not rewritten | 4 step 2, verified 4 step 7 |
| Banner hidden in either focus | 4 step 3 |
| Files nested `ResizablePanes` with its own storageKey | 5 |
| Files collapse button routed through `collapse` | 5 step 1 |
| `position: fixed` selection button verified | 5 step 4 |
| Gherkin: panel fills viewport, terminal survives | 3 |

No gaps.

**Type consistency:** `FocusTarget` / `focus` / `setFocus` / `toggleMain` / `togglePanel` are named identically in Task 1's module, Task 1's hook, and Task 4's call sites. `collapse` and its `'left' | 'right' | null` domain match across Task 2's prop, Task 2's test, Task 4's expression, and Task 5's usage. `data-testid="panel-maximize"` is declared in Task 3 and satisfied in Task 4. `data-pane="left"` is introduced in Task 2 step 3 and asserted in Task 2 step 1.

**Deliberate red window:** Tasks 1-3 leave the typecheck failing, because Task 1 deletes a hook that `SessionDetail` still imports until Task 4. This is called out in each affected step with the exact expected failure, so an implementer does not mistake it for their own breakage. The alternative — rewiring `SessionDetail` inside Task 1 — would merge the state machine and the page wiring into one unreviewable task.

**Placeholders:** none. Task 2 step 3's `{/* Splitter — unchanged */}` and Task 5 step 1's `{/* the existing sidebar div */}` are instructions not to edit surrounding code, not unspecified requirements.
