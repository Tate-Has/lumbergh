# Local "While You Were Away" Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the PWA is backgrounded and a session newly enters an attention state (unseen), fire a local system notification; tapping it opens that session.

**Architecture:** Frontend-only, reusing bite #4's `unseen`/`attentionState`. A pure `computeNotifications` decides what to fire; an app-wide `AttentionNotifier` polls `/sessions` and calls `registration.showNotification`; a tiny `notificationclick` handler (added via `workbox.importScripts`, no `injectManifest` migration) opens the session on tap; a self-contained General-settings toggle handles opt-in + permission.

**Tech Stack:** React/TypeScript, Vitest, vite-plugin-pwa (workbox generateSW), browser Notification + Service Worker APIs.

## Global Constraints

- Frontend-only; no backend changes (the `unseen`/`attentionState` fields already exist on the `/sessions` response).
- Fire **only when the tab is hidden** (`document.visibilityState === 'hidden'`) — never when foreground.
- Use `registration.showNotification` (mobile requires it; the `new Notification()` constructor is unsupported on Android Chrome).
- Opt-in preference is **per-device in localStorage** (key `lumbergh:notifyWhileAway`); OS grant via `Notification.requestPermission()` on a real user gesture (the toggle).
- Do NOT switch VitePWA to `injectManifest`; add the click handler via `workbox.importScripts`.
- Poll interval 10 s (matches the dashboard).
- Run `./lint.sh` clean before completion. Do not commit `frontend/package-lock.json` churn.
- Commit messages: no AI attribution / Co-Authored-By lines.

---

### Task 1: Pure notification-decision logic

**Files:**
- Create: `frontend/src/utils/attentionNotifications.ts`
- Test: `frontend/src/utils/attentionNotifications.test.ts`

**Interfaces:**
- Produces:
  - `NOTIFY_ENABLED_KEY = 'lumbergh:notifyWhileAway'`, `isNotifyEnabled(): boolean`, `setNotifyEnabled(v: boolean): void`.
  - `interface NotifiableSession { name: string; displayName?: string | null; unseen?: boolean; attentionState?: 'idle' | 'blocked' | 'error' | null }`
  - `interface NotificationSpec { title: string; body: string; tag: string; url: string }`
  - `interface NotifyContext { hidden: boolean; enabled: boolean; permissionGranted: boolean }`
  - `computeNotifications(prevUnseen: Set<string>, sessions: NotifiableSession[], ctx: NotifyContext): { toFire: NotificationSpec[]; nextUnseen: Set<string> }`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/utils/attentionNotifications.test.ts
import { describe, it, expect } from 'vitest'
import { computeNotifications } from './attentionNotifications'

const ctx = { hidden: true, enabled: true, permissionGranted: true }
const s = (name: string, attentionState: 'idle' | 'blocked' | 'error' = 'idle') => ({
  name,
  displayName: null,
  unseen: true,
  attentionState,
})

describe('computeNotifications', () => {
  it('fires for a newly-unseen session with a deep link', () => {
    const { toFire, nextUnseen } = computeNotifications(new Set(), [s('foo')], ctx)
    expect(toFire).toHaveLength(1)
    expect(toFire[0].title).toBe('foo')
    expect(toFire[0].body).toBe('Done — while you were away')
    expect(toFire[0].tag).toBe('foo')
    expect(toFire[0].url).toBe('/session/foo')
    expect(nextUnseen.has('foo')).toBe(true)
  })

  it('uses the attention verb for blocked/error', () => {
    expect(computeNotifications(new Set(), [s('b', 'blocked')], ctx).toFire[0].body).toBe(
      'Blocked — while you were away'
    )
    expect(computeNotifications(new Set(), [s('e', 'error')], ctx).toFire[0].body).toBe(
      'Failed — while you were away'
    )
  })

  it('coalesces multiple newly-unseen into one dashboard notification', () => {
    const { toFire } = computeNotifications(new Set(), [s('a'), s('b'), s('c')], ctx)
    expect(toFire).toHaveLength(1)
    expect(toFire[0].body).toBe('3 sessions need your attention')
    expect(toFire[0].url).toBe('/')
    expect(toFire[0].tag).toBe('lumbergh-attention')
  })

  it('does not re-fire for a session already unseen last poll', () => {
    const { toFire } = computeNotifications(new Set(['foo']), [s('foo')], ctx)
    expect(toFire).toHaveLength(0)
  })

  it('fires again if a session cleared then became unseen again', () => {
    // prev had foo; now foo is gone from unseen then... simulate re-entry:
    const first = computeNotifications(new Set(['foo']), [], ctx) // foo cleared
    expect(first.nextUnseen.has('foo')).toBe(false)
    const second = computeNotifications(first.nextUnseen, [s('foo')], ctx)
    expect(second.toFire).toHaveLength(1)
  })

  it('never fires when foreground, disabled, or permission not granted (but advances state)', () => {
    for (const bad of [
      { ...ctx, hidden: false },
      { ...ctx, enabled: false },
      { ...ctx, permissionGranted: false },
    ]) {
      const { toFire, nextUnseen } = computeNotifications(new Set(), [s('foo')], bad)
      expect(toFire).toHaveLength(0)
      expect(nextUnseen.has('foo')).toBe(true) // state still advances → no spam later
    }
  })

  it('ignores sessions that are not unseen', () => {
    const { toFire, nextUnseen } = computeNotifications(
      new Set(),
      [{ name: 'x', displayName: null, unseen: false, attentionState: null }],
      ctx
    )
    expect(toFire).toHaveLength(0)
    expect(nextUnseen.size).toBe(0)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/utils/attentionNotifications.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `attentionNotifications.ts`**

```typescript
// frontend/src/utils/attentionNotifications.ts
export const NOTIFY_ENABLED_KEY = 'lumbergh:notifyWhileAway'

export function isNotifyEnabled(): boolean {
  try {
    return localStorage.getItem(NOTIFY_ENABLED_KEY) === '1'
  } catch {
    return false
  }
}

export function setNotifyEnabled(v: boolean): void {
  try {
    localStorage.setItem(NOTIFY_ENABLED_KEY, v ? '1' : '0')
  } catch {
    // localStorage unavailable (private mode etc.) — preference just won't persist
  }
}

export interface NotifiableSession {
  name: string
  displayName?: string | null
  unseen?: boolean
  attentionState?: 'idle' | 'blocked' | 'error' | null
}

export interface NotificationSpec {
  title: string
  body: string
  tag: string
  url: string
}

export interface NotifyContext {
  hidden: boolean
  enabled: boolean
  permissionGranted: boolean
}

const VERB: Record<string, string> = { idle: 'Done', blocked: 'Blocked', error: 'Failed' }

export function computeNotifications(
  prevUnseen: Set<string>,
  sessions: NotifiableSession[],
  ctx: NotifyContext
): { toFire: NotificationSpec[]; nextUnseen: Set<string> } {
  const nextUnseen = new Set(sessions.filter((s) => s.unseen).map((s) => s.name))

  if (!ctx.enabled || !ctx.permissionGranted || !ctx.hidden) {
    return { toFire: [], nextUnseen }
  }

  const newly = [...nextUnseen].filter((name) => !prevUnseen.has(name))
  if (newly.length === 0) {
    return { toFire: [], nextUnseen }
  }

  if (newly.length === 1) {
    const session = sessions.find((s) => s.name === newly[0])!
    const verb = VERB[session.attentionState ?? 'idle'] ?? 'Done'
    return {
      toFire: [
        {
          title: session.displayName || session.name,
          body: `${verb} — while you were away`,
          tag: session.name,
          url: `/session/${encodeURIComponent(session.name)}`,
        },
      ],
      nextUnseen,
    }
  }

  return {
    toFire: [
      {
        title: 'Lumbergh',
        body: `${newly.length} sessions need your attention`,
        tag: 'lumbergh-attention',
        url: '/',
      },
    ],
    nextUnseen,
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/utils/attentionNotifications.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/attentionNotifications.ts frontend/src/utils/attentionNotifications.test.ts
git commit -m "feat(notify): pure while-you-were-away notification logic"
```

---

### Task 2: Service-worker click handler

**Files:**
- Create: `frontend/public/notification-click.js`
- Modify: `frontend/vite.config.ts` (VitePWA `workbox.importScripts`)

**Interfaces:** none (SW runtime glue).

- [ ] **Step 1: Write the click handler**

```javascript
// frontend/public/notification-click.js
// Imported into the generated service worker via workbox.importScripts.
// Opens (or focuses + navigates) the app to the session that finished.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const client of wins) {
        if ('focus' in client) {
          if ('navigate' in client) client.navigate(url)
          return client.focus()
        }
      }
      return self.clients.openWindow(url)
    })
  )
})
```

- [ ] **Step 2: Register it via workbox**

In `frontend/vite.config.ts`, add a `workbox` block to the `VitePWA({ ... })` options (alongside `registerType`, `devOptions`, `manifest`):

```typescript
    VitePWA({
      registerType: 'prompt',
      workbox: {
        importScripts: ['notification-click.js'],
      },
      devOptions: {
        enabled: true,
      },
      manifest: {
        // ...unchanged...
```

- [ ] **Step 3: Verify the build includes and imports it**

Run: `cd frontend && npm run build && grep -c "notification-click.js" dist/sw.js && ls dist/notification-click.js`
Expected: build succeeds; `dist/sw.js` references `notification-click.js` (count ≥ 1); the file exists in `dist/`.

- [ ] **Step 4: Commit**

```bash
git add frontend/public/notification-click.js frontend/vite.config.ts
git commit -m "feat(notify): service-worker notificationclick opens the session"
```

---

### Task 3: App-wide notifier

**Files:**
- Create: `frontend/src/components/AttentionNotifier.tsx`
- Modify: `frontend/src/App.tsx` (mount it)

**Interfaces:**
- Consumes: `computeNotifications`, `isNotifyEnabled` (Task 1); `getApiBase` (`src/config.ts`).
- Produces: a render-null component that polls `/sessions` app-wide and fires notifications.

- [ ] **Step 1: Implement `AttentionNotifier.tsx`**

```tsx
// frontend/src/components/AttentionNotifier.tsx
import { useEffect, useRef } from 'react'
import { getApiBase } from '../config'
import {
  computeNotifications,
  isNotifyEnabled,
  type NotifiableSession,
} from '../utils/attentionNotifications'

const POLL_MS = 10000

export default function AttentionNotifier() {
  const prevUnseen = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (!('Notification' in window) || !('serviceWorker' in navigator)) return
    let cancelled = false

    async function poll() {
      let sessions: NotifiableSession[] = []
      try {
        const res = await fetch(`${getApiBase()}/sessions`)
        if (!res.ok) return
        sessions = (await res.json()).sessions || []
      } catch {
        return
      }
      if (cancelled) return

      const { toFire, nextUnseen } = computeNotifications(prevUnseen.current, sessions, {
        hidden: document.visibilityState === 'hidden',
        enabled: isNotifyEnabled(),
        permissionGranted: Notification.permission === 'granted',
      })
      prevUnseen.current = nextUnseen
      if (toFire.length === 0) return

      try {
        const reg = await navigator.serviceWorker.ready
        for (const spec of toFire) {
          reg.showNotification(spec.title, {
            body: spec.body,
            tag: spec.tag,
            data: { url: spec.url },
          })
        }
      } catch {
        // Service worker not ready — skip this round.
      }
    }

    poll()
    const id = setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return null
}
```

- [ ] **Step 2: Mount it in `App.tsx`**

Add the import and render it beside `PWAUpdatePrompt`:

```tsx
import PWAUpdatePrompt from './components/PWAUpdatePrompt'
import AttentionNotifier from './components/AttentionNotifier'
```

```tsx
      <PWAUpdatePrompt />
      <AttentionNotifier />
    </>
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AttentionNotifier.tsx frontend/src/App.tsx
git commit -m "feat(notify): app-wide notifier polls and fires while backgrounded"
```

---

### Task 4: General-settings opt-in toggle

**Files:**
- Modify: `frontend/src/components/GeneralSettings.tsx`

**Interfaces:**
- Consumes: `isNotifyEnabled`, `setNotifyEnabled` (Task 1); the existing local `Toggle` component.

**Notes:** Self-contained — its own `useState` from localStorage, no new props threaded through `SettingsModal`, no backend. Insert after the "Session Navigator Dots" toggle row (`GeneralSettings.tsx:244`).

- [ ] **Step 1: Add imports and local state**

At the top of `GeneralSettings.tsx`, extend the React import and add the prefs helper import:

```tsx
import { useState } from 'react'
import { isNotifyEnabled, setNotifyEnabled } from '../utils/attentionNotifications'
```

Inside the `GeneralSettings` component body (near the top, with other hooks):

```tsx
  const [notifyOn, setNotifyOn] = useState<boolean>(() => isNotifyEnabled())
  const notifySupported = typeof window !== 'undefined' && 'Notification' in window
  const [notifyDenied, setNotifyDenied] = useState<boolean>(
    notifySupported && Notification.permission === 'denied'
  )

  const handleNotifyToggle = async (next: boolean) => {
    if (next && notifySupported && Notification.permission !== 'granted') {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') {
        setNotifyDenied(perm === 'denied')
        setNotifyEnabled(false)
        setNotifyOn(false)
        return
      }
    }
    setNotifyDenied(false)
    setNotifyEnabled(next)
    setNotifyOn(next)
  }
```

- [ ] **Step 2: Render the toggle row**

Immediately after the Session Navigator Dots block (the `</div>` closing its `flex items-center justify-between` row, `GeneralSettings.tsx:244`), insert:

```tsx
        <div className="flex items-center justify-between">
          <div>
            <label className="block text-sm text-text-tertiary">Notify while away</label>
            <p className="text-xs text-text-muted mt-0.5">
              System notification when a session needs attention. Fires only while the app is
              open in the background — not when it is fully closed.
            </p>
            {notifyDenied && (
              <p className="text-xs text-warning mt-0.5">
                Notifications are blocked in your browser settings for this site.
              </p>
            )}
          </div>
          <Toggle on={notifyOn} onChange={handleNotifyToggle} />
        </div>
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: exits 0. (`Toggle`'s `onChange` accepts `(value: boolean) => void`; `handleNotifyToggle` returns a promise, which is assignable — if tsc objects, wrap as `onChange={(v) => void handleNotifyToggle(v)}`.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/GeneralSettings.tsx
git commit -m "feat(notify): per-device notify-while-away settings toggle"
```

---

### Task 5: Full verification

- [ ] **Step 1: Frontend unit tests**

Run: `cd frontend && npx vitest run`
Expected: all PASS (includes the new `attentionNotifications` suite and the prior `sessionStatus` suite).

- [ ] **Step 2: Type-check + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: both succeed; `dist/sw.js` imports `notification-click.js`.

- [ ] **Step 3: Lint**

Run: `./lint.sh`
Expected: exits 0 (the pre-existing `CsvViewer.tsx` eslint warning is unrelated). Fix any new errors and re-run.

- [ ] **Step 4: Commit any lint fixups**

```bash
git add -A
git commit -m "chore(notify): lint cleanups"
```

(Skip if nothing changed. Do NOT sweep `frontend/package-lock.json` into the commit.)

---

## Self-Review

**Spec coverage:**
- Pure decision logic (newly-unseen, coalescing, verb, deep link) → Task 1. ✓
- Fires only when hidden + enabled + permission granted; advances state otherwise → Task 1 tests + `computeNotifications`. ✓
- `registration.showNotification` app-wide poll → Task 3. ✓
- Tap opens the session via `importScripts` click handler, no `injectManifest` → Task 2. ✓
- Per-device localStorage opt-in + `requestPermission` on gesture, in General settings → Task 4. ✓
- Known limitation noted in the toggle helper text → Task 4. ✓
- Frontend-only, no backend → all tasks. ✓

**Placeholder scan:** No TBD/TODO; Task 1 has complete tested code; Tasks 2-4 (browser/SW glue) show complete code and are verified via build/tsc/lint per the project's convention of unit-testing logic and not glue.

**Type consistency:** `NotifiableSession`/`NotificationSpec`/`NotifyContext` and `computeNotifications` signature (Task 1) are consumed unchanged by `AttentionNotifier` (Task 3); `isNotifyEnabled`/`setNotifyEnabled` (Task 1) used by both notifier (read) and settings (read/write) (Tasks 3-4); notification `data.url` set in Task 3 matches what `notification-click.js` reads in Task 2. ✓
```
