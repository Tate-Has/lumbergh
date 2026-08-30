# Troubleshooting

Common issues and how to fix them.

---

### Terminal not connecting?

Make sure tmux mouse mode is enabled:

```bash
tmux set -g mouse on
```

The bootstrap script does this automatically. If you skipped bootstrap, run it again.

---

### Port already in use?

The default port is **8420**. Pick a different one with:

```bash
lumbergh -p 9000
```

!!! note
    In dev mode, the backend runs on port **8420** and the Vite frontend on **5420**.

---

### Dependencies not installing?

Run `./bootstrap.sh` again -- it tells you what's missing.

For Node issues, make sure nvm is loaded first:

```bash
source ~/.nvm/nvm.sh
```

---

### Session shows as inactive?

The session's tmux session may have been killed externally. Click **Reset** on the session card to restart it.

---

### Git diff not updating?

- Make sure the session's working directory is a valid git repository.
- Check that `git` is installed and accessible from the shell.
- Diffs are cached in the background every 5 seconds. If you just made a change, wait a moment for the cache to refresh.

---

### Locked out after setting a password?

If you set a password and can't log in:

1. Stop Lumbergh
2. Edit `~/.config/lumbergh/settings.json` and clear the `"password"` field (set it to `""`)
3. Restart Lumbergh

Alternatively, unset the `LUMBERGH_PASSWORD` environment variable if that's how you configured it.

---

### AI status not working?

Configure an AI provider in **Settings > AI** tab.

For Ollama, make sure the server is running:

```bash
ollama serve
```

---

### Mobile can't connect?

Lumbergh binds to `0.0.0.0` by default, so it should be accessible from any device on your local network. If it's not:

- Check your firewall rules (e.g., `ufw`, `iptables`).
- For remote access outside your LAN, use [Tailscale](https://tailscale.com/).

---

### PWA not installable?

PWA installation requires HTTPS. Use Tailscale Serve for automatic TLS certificates:

```bash
tailscale serve --bg 8420
```

---

### Windows: `psmux` not found?

Lumbergh checks for `tmux` (Linux/macOS) or `psmux` (Windows) on startup and
exits with a hint if it's missing. Install psmux:

```powershell
uv tool install psmux
```

Then re-run `lumbergh`. If `psmux` is installed but still not found, make sure
the `uv` shims directory is on your `PATH` (run `uv tool dir --bin`).

---

### Windows: terminal session never appears?

If you see "Session not found" inside the dashboard but the session was just
created, this usually means `psmux`'s session listing returned an unexpected
format. Try:

1. Stop Lumbergh
2. Run `psmux kill-server` to clear any stale state
3. Restart Lumbergh and re-create the session

If it persists, check the backend log for a `psmux fallback` warning and
[file an issue](https://github.com/voglster/lumbergh/issues) with the
`psmux list-sessions` output.

---

### Terminal feels laggy?

Lumbergh runs a permanent watchdog that records any time the asyncio event
loop is blocked for more than 200ms. If the UI feels janky:

```bash
cat /tmp/lumbergh-lag.log
```

Each entry shows the offending thread stacks at the time of the stall.
Common causes: synchronous TinyDB writes, corrupt session JSON files in
`~/.config/lumbergh/session_data/`, or thread-pool exhaustion from too many
concurrent pane captures. Clear the log with `> /tmp/lumbergh-lag.log` to
validate a fix.

---

### Escape (or another key) never reaches the agent?

Some browser extensions intercept keys before any page can see them. The
classic offender is a Vim-style extension — **Vimium**, Vimium C, Surfingkeys,
Wasavi — which treats <kbd>Esc</kbd> as "leave insert mode" and implements it by
blurring the focused element:

```js
} else if ((event.type === "keydown") && KeyboardUtils.isEscape(event)) {
  if (DomUtils.isFocusable(activeElement)) {
    activeElement.blur();
  }
  ...
}
return this.suppressEvent;   // the page never receives the keydown
```

These run as content scripts at `document_start` on `<all_urls>`, so they are
ahead of every listener Lumbergh could register. Nothing in the app can
recover the key.

**The tell:** every other key types into the terminal normally, but Escape does
nothing *and* the terminal visibly loses focus. If instead the terminal keeps
focus and Escape simply has no effect, that is a different problem — see the
copy-mode note below.

**The fix:** exclude Lumbergh's origin in the extension's settings. In Vimium:
*Options → Excluded URLs and keys*, then add a rule whose pattern is your
Lumbergh URL and whose keys field is **empty**, which disables the extension on
that site:

```
https://lumbergh.example.ts.net/*
http://localhost:8420/*
http://localhost:5420/*
```

Leaving the keys field empty is deliberate. You can exclude only `<Esc>`, but a
page that is entirely a terminal wants none of the extension's other bindings
either — they fire the moment focus leaves the terminal.

To confirm the diagnosis before changing any settings, toggle the extension off
in `chrome://extensions` and press Escape; it starts working immediately, with
no reload.

!!! tip
    The on-screen **Esc** button in the terminal header keeps working even when
    the key is being swallowed. It sends the interrupt over HTTP
    (`POST /api/session/{name}/interrupt`) rather than through the terminal
    WebSocket, so it does not depend on the keyboard or on the socket being
    connected.

Other things that can swallow a key before the page: an OS or window-manager
global binding (on Hyprland, check `bind` lines and `submap`s in
`~/.config/hypr/`), and browser DevTools, which consumes Escape to toggle its
console drawer while it has focus. When debugging a missing key, close DevTools
first so it cannot be the cause.

---

### Escape does not stop the agent while you are scrolled up?

Different problem from the one above: here the key *does* reach the terminal.
Scrolling the pane puts tmux in copy-mode, and with `mode-keys vi` tmux binds
Escape to `clear-selection` — so it drops the selection and stays in the mode
instead of passing an Escape to the agent. Lumbergh handles this by leaving
copy-mode first (it sends `q` down the same socket) so the Escape lands on the
agent. If you see this on an older version, upgrade.

---

### Summoning Bill says `pi` is not installed?

Bill runs under a separate harness, not your normal coding agent — by default
[`pi`](https://github.com/badlogic/pi-mono), which you install yourself. Nothing
else in Lumbergh needs it, so a first summon is the only place you meet the
requirement, and the bare error reads like a broken install when it is not.

He is kept off your main agent on purpose: Bill supervises in a loop all day, and
that is only affordable on a cheap local model.

Two ways forward:

- **Install `pi`** and summon again.
- **Point Bill at the agent you already have** — Settings → Bill → Harness, set to
  e.g. `claude-code`. The summon dialog offers this as a one-click switch when it
  finds the harness missing. Expect it to cost more than `pi` would, since Bill
  polls continuously.
