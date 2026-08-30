/** Give jsdom tests a working `localStorage` global.
 *
 * Node 22+ defines its own experimental `globalThis.localStorage`, inert unless
 * the process was started with `--localstorage-file`. Vitest's jsdom environment
 * will not overwrite an own property that already exists on globalThis, so that
 * inert stub wins and jsdom's real storage never becomes the global. Because
 * `window === globalThis` under vitest, `window.localStorage` reads the stub too,
 * and both come back `undefined` — a test that touches localStorage fails with
 * "Cannot read properties of undefined" while `document` works perfectly, which
 * points suspicion at everything except the actual cause.
 *
 * jsdom's storage is reachable the whole time via the `jsdom` handle vitest hangs
 * on the window, so republish it under the name the code expects. */
const jsdomWindow = (globalThis as { jsdom?: { window: Window } }).jsdom?.window

if (jsdomWindow) {
  for (const key of ['localStorage', 'sessionStorage'] as const) {
    Object.defineProperty(globalThis, key, {
      configurable: true,
      get: () => jsdomWindow[key],
    })
  }
}
