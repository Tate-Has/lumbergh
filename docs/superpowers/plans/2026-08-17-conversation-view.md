# Term / Conv Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the conversation a peer view of the terminal — one toggle, sticky, zoomable, and fast on long sessions.

**Architecture:** A `useSessionView()` hook holds `'term' | 'conv'` in localStorage and owns an Alt+V window listener. The left pane renders both views simultaneously, hiding the inactive one, so the terminal's xterm instance and WebSocket survive every swap. The conversation feed is virtualized with `@tanstack/react-virtual`. The `'activity'` right-panel tab is removed everywhere.

**Tech Stack:** React 19 + TypeScript, Vite, Tailwind, `@tanstack/react-virtual`, xterm.js, vitest, Playwright + pytest-bdd.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-17-conversation-view-design.md`. Read it before starting.
- The two views are named **Term** and **Conv** in all user-facing text — buttons, tooltips, labels. Never "Terminal"/"Conversation" in UI copy, never "Activity".
- Swapping views must NEVER unmount `Terminal`. Unmounting tears down xterm and the WebSocket, losing scrollback and reconnecting the session. This regression had to be fixed twice during zen mode.
- `localStorage` keys, exactly: `lumbergh:sessionView` (values `'term'` / `'conv'`), `lumbergh:conversationFontSize`. The terminal's existing `terminal-font-size` key is unchanged.
- Keyboard chords match on `e.code`, never `e.key` — on macOS, Option+V reports `e.key === '√'`. See the comment already in `frontend/src/utils/terminalChords.ts`.
- Backend is untouched by every task in this plan. No Python file changes.
- Run `./lint.sh` from the repo root before every commit.
- Dev servers (vite :5420, backend :8420) are already running in a user-managed tmux window — never start, restart, or kill them.
- `backend/lumbergh/frontend_dist/` is a gitignored prebuilt bundle that `:8420` serves in preference to `frontend/dist`, and it goes stale. Rebuild and resync it via `build.sh`'s copy step before any browser-based verification, or you will be testing old code.

---

### Task 1: The view hook and its chord

`useSessionView` owns the `'term' | 'conv'` state, its persistence, and Alt+V. Alt+V must also join `isSessionCycleChord` so xterm declines it and it reaches the window listener instead of arriving at tmux as `\x1bv`.

**Files:**
- Create: `frontend/src/hooks/useSessionView.ts`
- Modify: `frontend/src/utils/terminalChords.ts`
- Test: `frontend/src/utils/terminalChords.test.ts`

**Interfaces:**
- Consumes: `useIsDesktop` from `../hooks/useMediaQuery`; the existing `isSessionCycleChord(event: KeyboardEvent): boolean`.
- Produces: `useSessionView(): { view: SessionView; setView: (v: SessionView) => void; toggleView: () => void }` and `type SessionView = 'term' | 'conv'`, both exported from `frontend/src/hooks/useSessionView.ts`.

- [ ] **Step 1: Write the failing chord test**

Add to `frontend/src/utils/terminalChords.test.ts`, inside the existing `describe`:

```ts
  it('claims Alt+V so the view toggle fires instead of tmux seeing \\x1bv', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: 'v', code: 'KeyV' }))).toBe(true)
  })

  it('claims Option+V on macOS, where the key character is not "v"', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: '√', code: 'KeyV' }))).toBe(true)
  })

  it('lets a bare v and Ctrl+V through to the shell', () => {
    expect(isSessionCycleChord(chord({ key: 'v', code: 'KeyV' }))).toBe(false)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: 'v', code: 'KeyV' }))).toBe(false)
  })
```

Ctrl+V must stay false — it is paste.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/utils/terminalChords.test.ts
```

Expected: FAIL — the three new Alt+V cases return `false`.

- [ ] **Step 3: Claim the chord**

In `frontend/src/utils/terminalChords.ts`, extend the final return so Alt+V is claimed alongside Alt+Z. Keep the existing Ctrl+[ / Ctrl+] and Alt+Arrow branches exactly as they are — they are deliberately meta-agnostic and were settled in a prior review:

```ts
  const altOnly = event.altKey && !event.ctrlKey && !event.metaKey
  return altOnly && (event.code === 'KeyZ' || event.code === 'KeyV')
```

Extend the existing `e.code` comment to cover V as well as Z, rather than adding a second comment.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/utils/terminalChords.test.ts
```

Expected: PASS, all cases.

- [ ] **Step 5: Write the hook**

Create `frontend/src/hooks/useSessionView.ts`. Modeled on `frontend/src/hooks/useZenMode.ts` — read that file first and follow its shape:

```ts
import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'lumbergh:sessionView'

export type SessionView = 'term' | 'conv'

/** Which rendering of the session the main pane shows: the raw terminal, or the
 * conversation feed. Both stay mounted; this only picks which one is visible.
 *
 * Stored per browser rather than per session — it is a viewing preference, not a
 * property of any one session. */
export function useSessionView() {
  const [view, setViewState] = useState<SessionView>(() =>
    localStorage.getItem(STORAGE_KEY) === 'conv' ? 'conv' : 'term'
  )

  const setView = useCallback((next: SessionView) => {
    setViewState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }, [])

  const toggleView = useCallback(
    () => setView(view === 'term' ? 'conv' : 'term'),
    [view, setView]
  )

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      if (e.code !== 'KeyV') return
      e.preventDefault()
      setView(view === 'term' ? 'conv' : 'term')
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [view, setView])

  return { view, setView, toggleView }
}
```

Unlike `useZenMode`, this hook is NOT gated on `useIsDesktop` — the toggle works on mobile too.

- [ ] **Step 6: Typecheck and commit**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
cd /home/jvogel/src/personal/lumbergh && ./lint.sh
git add frontend/src/hooks/useSessionView.ts frontend/src/utils/terminalChords.ts frontend/src/utils/terminalChords.test.ts
git commit -m "feat(view): session view hook and alt+v chord"
```

---

### Task 2: Rename activity to conversation, split the file

A pure refactor: no behavior changes, no new features. Doing it on its own keeps the behavior tasks' diffs readable. `ActivityFeed.tsx` is 267 lines and virtualization will push it well past that, so the cards move to their own file now.

**Files:**
- Create: `frontend/src/components/conversation/ConversationView.tsx` (from `activity/ActivityFeed.tsx`, shell only)
- Create: `frontend/src/components/conversation/ConversationItem.tsx` (from `activity/ActivityFeed.tsx`, cards only)
- Create: `frontend/src/components/conversation/ConversationRespondBox.tsx` (from `activity/ActivityRespondBox.tsx`)
- Create: `frontend/src/hooks/useConversationSocket.ts` (from `hooks/useActivitySocket.ts`)
- Delete: `frontend/src/components/activity/` and `frontend/src/hooks/useActivitySocket.ts`
- Modify: `frontend/src/pages/SessionDetail.tsx:18` (import path only)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: default export `ConversationView({ sessionName }: { sessionName: string })` from `components/conversation/ConversationView.tsx`; named export `Item({ item }: { item: RenderItem })` from `components/conversation/ConversationItem.tsx`; `useConversationSocket`, `mergeEvents`, and the types `ActivityEvent`, `ToolItem`, `RenderItem` from `hooks/useConversationSocket.ts`.

Keep the type names `ActivityEvent` / `ToolItem` / `RenderItem` as they are. They describe transcript events, not the view, and renaming them ripples into `mergeEvents` and its tests for no gain.

- [ ] **Step 1: Move the files with git mv**

```bash
cd /home/jvogel/src/personal/lumbergh/frontend/src
mkdir -p components/conversation
git mv components/activity/ActivityFeed.tsx components/conversation/ConversationView.tsx
git mv components/activity/ActivityRespondBox.tsx components/conversation/ConversationRespondBox.tsx
git mv hooks/useActivitySocket.ts hooks/useConversationSocket.ts
rmdir components/activity
```

`git mv` preserves history, which a create-and-delete does not.

- [ ] **Step 2: Rename the symbols**

In the moved files:
- `useConversationSocket.ts`: rename the exported hook `useActivitySocket` → `useConversationSocket`. Leave `mergeEvents` and all type names alone.
- `ConversationRespondBox.tsx`: rename the component `ActivityRespondBox` → `ConversationRespondBox`.
- `ConversationView.tsx`: rename the component `ActivityFeed` → `ConversationView`; update its imports to `useConversationSocket` and `ConversationRespondBox`.
- `pages/SessionDetail.tsx:18`: change the import to `import ConversationView from '../components/conversation/ConversationView'` and update its two JSX call sites (currently `<ActivityFeed ... />` at lines ~523 and ~660) to `<ConversationView ... />`.

- [ ] **Step 3: Split the cards out**

Move these from `ConversationView.tsx` into a new `components/conversation/ConversationItem.tsx`, unchanged in behavior: `TOOL_ICONS`, `parseToolInput`, `statusMark`, `cardShell`, `BashCard`, `DiffLines`, `EditCard`, `GenericToolCard`, `ToolCard`, `ThinkingBlock`, `AgentMarkdown`, and `Item`.

Export only `Item` — everything else is internal to that file. `ConversationView.tsx` then imports `import { Item } from './ConversationItem'` and keeps only the shell: `ConversationView`, its scroll/follow effects, the `noTranscript` branch, and the respond box.

- [ ] **Step 4: Verify nothing broke**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
grep -rn "ActivityFeed\|useActivitySocket\|ActivityRespondBox\|components/activity" src/ || echo "no stale references"
```

Expected: clean typecheck, all tests pass, and the grep prints "no stale references".

- [ ] **Step 5: Commit**

```bash
cd /home/jvogel/src/personal/lumbergh && ./lint.sh
git add -A frontend/src
git commit -m "refactor(conv): rename activity to conversation, split cards out of the shell"
```

---

### Task 3: Failing UI test for the swap

Feature-first red-green. The feature does not exist yet; this test is committed failing and Task 4 turns it green.

**Files:**
- Create: `test/e2e-ui/features/session_view.feature`
- Create: `test/e2e-ui/test_session_view.py`

**Interfaces:**
- Consumes: shared steps in `test/e2e-ui/conftest.py` — `Given a test session exists` and `Given I am on the session page for "{name}"` (line 168). Existing test ids `terminal-container` and `xterm-container`.
- Produces: the test-id contract Task 4 must satisfy — `view-toggle` on the button, `conversation-view` on the feed root.

- [ ] **Step 1: Write the feature file**

Create `test/e2e-ui/features/session_view.feature`:

```gherkin
Feature: Term and Conv views
  As a user I want the session rendered either as a raw terminal or as a
  readable conversation, without losing my session when I switch.

  Scenario: The toggle swaps between Term and Conv
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    Then I should see the terminal container
    When I click the view toggle
    Then I should see the conversation view
    And I should not see the terminal container

  Scenario: The view choice sticks across a reload
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    When I click the view toggle
    And I reload the page
    Then I should see the conversation view

  Scenario: Swapping back returns to a still-connected terminal
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    When I click the view toggle
    And I click the view toggle
    Then I should see the terminal container
    And the terminal is connected
```

- [ ] **Step 2: Write the step definitions**

Create `test/e2e-ui/test_session_view.py`. Note that pytest-bdd does not resolve steps across test modules, so every step not defined in `conftest.py` must be defined here:

```python
"""Term/Conv session view step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import scenarios, then, when

scenarios("features/session_view.feature")


@when("I click the view toggle")
def click_view_toggle(page: Page):
    page.locator('[data-testid="view-toggle"]').click()


@when("I reload the page")
def reload_page(page: Page):
    page.reload()
    page.wait_for_load_state("networkidle")


@then("I should see the terminal container")
def see_terminal_container(page: Page):
    expect(page.locator('[data-testid="terminal-container"]')).to_be_visible(timeout=10000)


@then("I should not see the terminal container")
def no_terminal_container(page: Page):
    expect(page.locator('[data-testid="terminal-container"]')).not_to_be_visible(timeout=10000)


@then("I should see the conversation view")
def see_conversation_view(page: Page):
    expect(page.locator('[data-testid="conversation-view"]')).to_be_visible(timeout=10000)


@then("the terminal is connected")
def terminal_connected(page: Page):
    expect(page.locator('[data-testid="xterm-container"]')).to_be_visible(timeout=10000)
```

`not_to_be_visible` rather than `to_have_count(0)`: the terminal stays in the DOM by design and is only hidden. A count assertion would demand an unmount, which is exactly what must not happen.

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd test/e2e-ui && .venv/bin/python -m pytest test_session_view.py -v --base-url http://localhost:8420 --repo-dir "$HOME"
```

Expected: scenario one FAILS at `I click the view toggle` — no element has `data-testid="view-toggle"` yet.

If the run errors on fixtures, a missing venv, or a bad `--repo-dir`, that is a broken test, not a red one. Fix the invocation and re-run until the only failure is the missing toggle. If `test/e2e-ui/.venv` does not exist, create it with `uv` and install `requirements.txt` plus Playwright's chromium.

- [ ] **Step 4: Commit the failing test**

```bash
cd /home/jvogel/src/personal/lumbergh
git add test/e2e-ui/features/session_view.feature test/e2e-ui/test_session_view.py
git commit -m "test(view): failing UI test for term/conv swap"
```

---

### Task 4: Wire the swap up

Turns Task 3 green. Both views render simultaneously; the inactive one is hidden, never unmounted. `'activity'` is removed from the tab systems.

**Files:**
- Modify: `frontend/src/components/TerminalHeader.tsx` (toggle button)
- Modify: `frontend/src/components/Terminal.tsx` (pass the toggle props through)
- Modify: `frontend/src/pages/SessionDetail.tsx` (render both views; remove the activity tab)
- Test: `frontend/src/components/conversation/sessionViewMount.test.tsx`

**Interfaces:**
- Consumes: `useSessionView()` and `SessionView` from Task 1; `ConversationView` from Task 2.
- Produces: `data-testid="view-toggle"` on the header button and `data-testid="conversation-view"` on the conversation root — both required by Task 3's test.

- [ ] **Step 1: Add the toggle button to the header**

In `frontend/src/components/TerminalHeader.tsx`, add two props to the props interface — `view: 'term' | 'conv'` and `onToggleView: () => void` — and render this button as the FIRST control in the right-hand control group (the `<div className="flex items-center gap-2 shrink-0">` that currently starts with the pop-out button, around line 154). Import `MessageSquare` and `SquareTerminal` from `lucide-react`:

```tsx
      <button
        onClick={onToggleView}
        data-testid="view-toggle"
        className="w-8 h-8 rounded-[var(--radius-md)] bg-control-bg hover:bg-control-bg-hover flex items-center justify-center text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
        title={view === 'term' ? 'Switch to Conv (Alt+V)' : 'Switch to Term (Alt+V)'}
      >
        {view === 'term' ? <MessageSquare size={14} /> : <SquareTerminal size={14} />}
      </button>
```

The icon shows the DESTINATION, not the current view — in Term you see the conversation icon.

- [ ] **Step 2: Thread the props through Terminal**

`TerminalHeader` is rendered by `Terminal` (around line 1016), so `Terminal` needs to pass them. Add `view?: 'term' | 'conv'` and `onToggleView?: () => void` to `Terminal`'s props interface, destructure them with defaults `view = 'term'` and `onToggleView = () => {}`, and forward both to `<TerminalHeader ... />`.

- [ ] **Step 3: Render both views in SessionDetail**

In `frontend/src/pages/SessionDetail.tsx`:

Import and call the hook next to the other hooks near line 73:

```ts
import { useSessionView } from '../hooks/useSessionView'
// ...
const { view, toggleView } = useSessionView()
```

Pass the toggle props and the visibility flag into `Terminal` inside `renderTerminal()`, alongside the existing props:

```tsx
  view={view}
  onToggleView={toggleView}
  isVisible={view === 'term' && (isDesktop || mobileTab === 'terminal')}
```

Then change `renderTerminal()` so it returns BOTH views, with the inactive one hidden:

```tsx
  const renderTerminal = () => (
    <div className="h-full relative">
      <div className={`h-full ${view === 'term' ? '' : 'hidden'}`} data-testid="terminal-container">
        {/* the existing terminal JSX, unchanged, minus its own data-testid */}
      </div>
      <div className={`h-full ${view === 'conv' ? '' : 'hidden'}`}>
        {name && <ConversationView sessionName={name} />}
      </div>
    </div>
  )
```

Move the existing `data-testid="terminal-container"` onto the terminal's wrapper div so it hides with the terminal — Task 3's test asserts it becomes invisible, and an always-visible outer div would fail that.

Do NOT key either view on `view`, and do not conditionally mount them. Both stay mounted for the life of the page.

- [ ] **Step 4: Tag the conversation root**

In `frontend/src/components/conversation/ConversationView.tsx`, add `data-testid="conversation-view"` to the outermost `div` of the main return (the `relative flex h-full flex-col` one). Add it to the `noTranscript` early-return div as well, so the test passes on a session with no transcript yet.

- [ ] **Step 5: Remove the activity tab**

In `frontend/src/pages/SessionDetail.tsx`:
- Line 25: `type RightPanel = 'git' | 'files' | 'todos' | 'prompts' | 'shared'`
- Line 26: `type MobileTab = 'terminal' | 'git' | 'files' | 'todos' | 'prompts' | 'shared'`
- Line 36: delete the `{ id: 'activity', label: 'Activity' }` entry from `ALL_TABS`
- Line 45: delete `activity: false,` from `DEFAULT_TAB_VISIBILITY`
- Lines 76-91: in the `rightPanel` initializer, delete the `saved === 'activity'` clause. A saved `'activity'` now falls through to the `return 'git'` default, which is the migration the spec asks for — no extra code needed.
- Lines 189-197: simplify `visibleMobileTabs` to drop the special-cased Activity entry:

```tsx
  const visibleMobileTabs = useMemo(
    () =>
      [{ id: 'terminal' as MobileTab, label: 'Term' }].concat(
        ALL_TABS.filter((t) => effectiveTabVisibility[t.id] !== false)
      ),
    [effectiveTabVisibility]
  )
```

- Line ~523: delete the `{mobileTab === 'activity' && ...}` line from `renderMobileTabContent`
- Line ~660: delete the `{rightPanel === 'activity' && ...}` line from `renderRightPanel`

The mobile terminal tab's label becomes `Term`, per the naming constraint.

- [ ] **Step 6: Write the mount-count test**

Create `frontend/src/components/conversation/sessionViewMount.test.tsx`. This guards the plan's hardest constraint: a swap must not remount the terminal.

The repo's vitest config uses `environment: 'node'`, so this test needs jsdom and React Testing Library. Install them as dev dependencies and set the environment for this file with a docblock pragma rather than changing the global config:

```bash
cd frontend && npm install -D jsdom @testing-library/react
```

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest'
import { useEffect, useState } from 'react'
import { render, act } from '@testing-library/react'

let mountCount = 0

function FakeTerminal() {
  useEffect(() => {
    mountCount += 1
  }, [])
  return <div>terminal</div>
}

/** Mirrors the shape of SessionDetail's renderTerminal: both views always
 * mounted, the inactive one hidden with a class. */
function Pane({ view }: { view: 'term' | 'conv' }) {
  return (
    <div className="h-full relative">
      <div className={view === 'term' ? '' : 'hidden'}>
        <FakeTerminal />
      </div>
      <div className={view === 'conv' ? '' : 'hidden'}>conversation</div>
    </div>
  )
}

function Harness() {
  const [view, setView] = useState<'term' | 'conv'>('term')
  return (
    <>
      <button onClick={() => setView((v) => (v === 'term' ? 'conv' : 'term'))}>swap</button>
      <Pane view={view} />
    </>
  )
}

describe('session view swapping', () => {
  it('never remounts the terminal', () => {
    mountCount = 0
    const { getByText } = render(<Harness />)
    act(() => getByText('swap').click())
    act(() => getByText('swap').click())
    expect(mountCount).toBe(1)
  })
})
```

- [ ] **Step 7: Prove the test has teeth**

A mount-count test that cannot fail is worthless. Temporarily change `Pane` to conditionally render — `{view === 'term' && <FakeTerminal />}` instead of the hidden-class wrapper — and re-run. It must fail with `expected 3 to be 1`. Quote that output in your report, then restore the correct version and confirm it passes again.

- [ ] **Step 8: Run everything**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
```

Then rebuild and resync `backend/lumbergh/frontend_dist` via `build.sh`'s copy step, and run the UI test:

```bash
cd test/e2e-ui && .venv/bin/python -m pytest test_session_view.py -v --base-url http://localhost:8420 --repo-dir "$HOME"
```

Expected: all three scenarios PASS. Never edit the test to make it pass; if you believe the test is wrong, stop and report NEEDS_CONTEXT.

- [ ] **Step 9: Commit**

```bash
cd /home/jvogel/src/personal/lumbergh && ./lint.sh
git add -A frontend test
git commit -m "feat(view): term/conv toggle with both views mounted"
```

---

### Task 5: View-aware zoom

One zoom control in the header, driving the terminal's font size in Term and the conversation's scale in Conv.

**Files:**
- Modify: `frontend/src/components/conversation/ConversationView.tsx`
- Modify: `frontend/src/components/TerminalHeader.tsx`
- Modify: `frontend/src/components/Terminal.tsx`

**Interfaces:**
- Consumes: `view` from Task 4, already threaded into `TerminalHeader`.
- Produces: nothing later tasks depend on. Task 6 must preserve the `zoom` style set here.

- [ ] **Step 1: Find the existing zoom control**

Read `frontend/src/components/TerminalHeader.tsx` and locate the font-size control in the expanded second row (the component starting around line 241). Note its exact markup and the `fontSize` / `onFontSizeChange` props it uses. You are extending this control, not building a new one.

- [ ] **Step 2: Scale the conversation with CSS zoom**

In `ConversationView.tsx`, read the persisted scale and apply it to the root element:

```tsx
const [scale, setScale] = useState(() => {
  const saved = parseFloat(localStorage.getItem('lumbergh:conversationFontSize') ?? '')
  return !isNaN(saved) && saved >= 0.6 && saved <= 2 ? saved : 1
})
```

Apply it as `style={{ zoom: scale }}` on the same outer div that carries `data-testid="conversation-view"`.

CSS `zoom` rather than a `fontSize` on the container: Tailwind's text sizes are `rem`-based and resolve against the root element, so a container `fontSize` would not move them. `zoom` scales text, padding, and gaps together, which is what "see more or less at once" actually means. It is supported in all current browsers (Firefox since 126).

- [ ] **Step 3: Lift the scale so the header can drive it**

The header cannot reach `ConversationView`'s local state, so the scale must live in `SessionDetail` beside `view` and be passed down. Move the `useState` initializer from Step 2 into `SessionDetail.tsx`, persist on change, and pass `scale` to `ConversationView` as a prop and `scale`/`onScaleChange` down through `Terminal` into `TerminalHeader` — the same threading path Task 4 used for `view` and `onToggleView`.

- [ ] **Step 4: Make the control view-aware**

In `TerminalHeader`'s font-size control, when `view === 'conv'` the +/− buttons call `onScaleChange` with `scale ± 0.1` clamped to `[0.6, 2]`, and the readout shows a percentage (`Math.round(scale * 100)%`). When `view === 'term'` it drives `onFontSizeChange` exactly as it does today. The manual "fit" action is terminal-only — hide it when `view === 'conv'`.

- [ ] **Step 5: Verify in the browser**

Rebuild and resync `frontend_dist`. Then, in Conv view, press the zoom controls and confirm text, padding, and card spacing all scale together and the value survives a reload. Switch to Term and confirm the same control still changes the terminal font size and that the two values are independent. Screenshot both.

- [ ] **Step 6: Commit**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
cd /home/jvogel/src/personal/lumbergh && ./lint.sh
git add -A frontend
git commit -m "feat(conv): view-aware zoom control"
```

---

### Task 6: Virtualize the conversation

The feed renders every item today. As a primary full-height view with zoom, long sessions must not stutter.

**Files:**
- Modify: `frontend/src/components/conversation/ConversationView.tsx`
- Test: `frontend/src/components/conversation/conversationVirtual.test.tsx`

**Interfaces:**
- Consumes: everything from Tasks 2, 4, and 5. The `zoom` style from Task 5 stays on the root; the virtualizer's scroll element is the inner scroll container, not the zoomed root.
- Produces: nothing.

- [ ] **Step 1: Read the house precedent**

`frontend/src/components/CsvViewer.tsx:72` already uses `useVirtualizer`. Follow its import and configuration style.

- [ ] **Step 2: Write the failing virtualization test**

Create `frontend/src/components/conversation/conversationVirtual.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import ConversationView from './ConversationView'

vi.mock('../../hooks/useConversationSocket', () => ({
  useConversationSocket: () => ({
    items: Array.from({ length: 500 }, (_, i) => ({
      id: String(i),
      type: 'status' as const,
      text: `event ${i}`,
    })),
    noTranscript: false,
    isConnected: true,
  }),
}))

describe('ConversationView', () => {
  it('renders a window of rows, not all 500', () => {
    const { container } = render(<ConversationView sessionName="x" scale={1} />)
    const rendered = container.querySelectorAll('[data-index]')
    expect(rendered.length).toBeGreaterThan(0)
    expect(rendered.length).toBeLessThan(100)
  })
})
```

- [ ] **Step 3: Run it to verify it fails**

```bash
cd frontend && npx vitest run src/components/conversation/conversationVirtual.test.tsx
```

Expected: FAIL — no `[data-index]` elements exist, so the count is 0 and `toBeGreaterThan(0)` fails.

- [ ] **Step 4: Virtualize**

In `ConversationView.tsx`, replace the plain `.map()` over `visibleItems` with a virtualizer. Keep `scrollRef` as the scroll element and keep the `overscroll-contain` class on it:

```tsx
const virtualizer = useVirtualizer({
  count: visibleItems.length,
  getScrollElement: () => scrollRef.current,
  estimateSize: () => 80,
  overscan: 8,
})

// inside the scroll container:
<div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
  {virtualizer.getVirtualItems().map((row) => (
    <div
      key={visibleItems[row.index].id}
      data-index={row.index}
      ref={virtualizer.measureElement}
      style={{ position: 'absolute', top: 0, left: 0, width: '100%', transform: `translateY(${row.start}px)` }}
      className="px-3 py-1.5"
    >
      <Item item={visibleItems[row.index]} />
    </div>
  ))}
</div>
```

`measureElement` handles dynamic heights: TanStack v3 attaches a `ResizeObserver` to each measured element, so a card expanding or collapsing and a zoom change both re-measure automatically. Do not add your own observer.

- [ ] **Step 5: Rebuild follow-to-bottom**

The old follow logic observed a content element that no longer exists. Delete that `ResizeObserver` effect and replace it with a scroll to the last index whenever the item count grows while following:

```tsx
useEffect(() => {
  if (!followingRef.current || visibleItems.length === 0) return
  programmaticRef.current = true
  virtualizer.scrollToIndex(visibleItems.length - 1, { align: 'end' })
  requestAnimationFrame(() => {
    programmaticRef.current = false
  })
}, [visibleItems.length, virtualizer])
```

Keep unchanged: the `onScroll` handler and its 40px at-bottom check, `followingRef`, `programmaticRef`, and the "Jump to latest ↓" button — but change that button's click handler to call `virtualizer.scrollToIndex(visibleItems.length - 1, { align: 'end' })` instead of setting `scrollTop`.

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/components/conversation/conversationVirtual.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Verify follow behavior in a real browser**

This is the part unit tests cannot settle. Rebuild and resync `frontend_dist`, then open a session with a long transcript in Conv view and confirm all of:

1. Scrolling up through several hundred items is smooth, with no blank gaps or overlapping rows.
2. Expanding a Bash or Edit card pushes the rows below it down cleanly, without overlap.
3. While pinned to the bottom, new events keep the view pinned.
4. Scrolling up detaches follow and shows "Jump to latest ↓"; clicking it returns to the bottom and re-attaches.
5. Changing zoom does not leave rows overlapping or stranded mid-feed.

Report what you observed for each. If any fail, the fix belongs in the measure/follow interaction — do not disable virtualization to make them pass.

- [ ] **Step 8: Commit**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
cd /home/jvogel/src/personal/lumbergh && ./lint.sh
git add -A frontend
git commit -m "perf(conv): virtualize the conversation feed"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Term/Conv naming in all UI copy | 4 (button titles, mobile tab label), 5 (zoom readout) |
| Icon button showing destination view | 4 |
| Alt+V toggles, declined by xterm | 1 |
| Sticky, global, per-browser via `lumbergh:sessionView` | 1 |
| Zoom targets active view; separate persisted values | 5 |
| Zen needs no changes | none needed — zen collapses the right panel and is orthogonal |
| Swapping never disconnects the session | 4 (both mounted + mount-count test with teeth) |
| `activity` removed from right tabs, mobile tabs, gear menu | 4 |
| Saved `rightPanel: 'activity'` migrates to `'git'` | 4 step 5 |
| Backend `tabVisibility.activity` left inert | no task — deliberate no-op |
| `activity/` → `conversation/`, split shell from cards | 2 |
| `useActivitySocket` → `useConversationSocket`, endpoint unchanged | 2 |
| Virtualize with `measureElement` | 6 |
| Follow-to-bottom rebuilt | 6 step 5 |
| Gherkin: swap, stickiness, still-connected | 3 |
| Mount-count test with negative control | 4 steps 6-7 |
| Virtualization windowing test | 6 |
| macOS `e.code` chord test | 1 |

No gaps.

**Type consistency:** `SessionView` / `view` / `setView` / `toggleView` are named identically in Task 1's hook and Tasks 4-5's call sites. `view` and `onToggleView` match across `TerminalHeader`'s props, `Terminal`'s props, and `SessionDetail`'s JSX. `scale` / `onScaleChange` match across Task 5's three files. `data-testid` values `view-toggle` and `conversation-view` are declared in Task 3 and satisfied in Task 4. `ConversationView`'s `scale` prop is introduced in Task 5 step 3 and used by Task 6's test — Task 6 depends on Task 5 having landed, which the ordering guarantees.

**Placeholders:** none. Task 4 step 3's `{/* the existing terminal JSX, unchanged */}` is an instruction not to edit surrounding code, not an unspecified requirement.

**One risk worth naming:** Task 4 step 6 adds `jsdom` and `@testing-library/react` as dev dependencies — the repo has no component tests today. This is a real, if small, expansion of the test toolchain, justified because the no-remount guarantee cannot be verified any other way and has already regressed twice.
