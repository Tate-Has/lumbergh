# Lumbergh

**Micromanage your AI interns.**

A self-hosted web dashboard for supervising multiple Claude Code sessions running in tmux. Watch diffs roll in, fire off prompts, check todos, and keep your AI workers on task -- all from your browser (or your phone).

![Lumbergh Dashboard](docs/screenshots/dashboard.png)

## Install in 30 seconds

You need `tmux` and `git` on your machine. Then:

```bash
uv tool install pylumbergh
lumbergh
```

Open **http://localhost:8420**. Done.

> No `uv`? Use `pip install pylumbergh` instead. Lumbergh checks for tmux/git on startup and tells you what's missing.

## What you get

- **Multi-session dashboard** -- all your Claude Code sessions at a glance, with live status detection
- **Live terminals** -- interact with real terminal sessions via xterm.js + WebSockets
- **Git diff viewer** -- watch diffs, commits, and branch changes as the AI writes code
- **Git graph** -- interactive commit history visualization
- **File browser** -- browse project files with syntax highlighting
- **Manager AI** -- built-in AI chat pane for reviewing and coordinating work across sessions
- **Prompt templates** -- reusable prompts with variables, fire them with one click
- **Todos & scratchpad** -- per-project notes and task tracking
- **Shared files** -- share context across sessions
- **Mobile-first + PWA** -- responsive design, installable on your phone or tablet
- **Dark and light themes** -- toggle with one click

## Mobile / PWA setup

Lumbergh works great as a PWA -- add it to your home screen and it runs fullscreen like a native app. This requires HTTPS, but you don't need to expose anything to the internet.

[Tailscale](https://tailscale.com/) is a free VPN that connects your devices into a private network (your "tailnet"). Install it on your server and your phone, and they can talk directly -- no port forwarding, no firewall holes, no public IP needed. Tailscale also provides free HTTPS certificates for your machines, which is what makes the PWA work.

### Production (recommended)

One command. Tailscale terminates TLS and proxies to Lumbergh automatically:

```bash
tailscale serve --bg 8420
```

Access Lumbergh at `https://YOUR-MACHINE.tailnet-name.ts.net`. Valid certs, auto-renewed, only accessible from your tailnet. Then open Chrome on your phone, tap the menu, and choose **"Install app"** or **"Add to Home Screen"**.

> Find your machine's Tailscale name with `tailscale status --self`.

### Development

The Vite dev server needs cert files directly. Run the setup script -- it detects your Tailscale hostname automatically:

```bash
./setup-https.sh
```

Restart the frontend and open the URL it prints. Re-run every ~90 days to renew the certs.

### Without Tailscale

Lumbergh binds to `0.0.0.0` so it's accessible from any device on your local network. Without HTTPS you can still use it in the browser -- you just won't get the PWA install option.

## Development

Want to contribute or hack on Lumbergh?

```bash
git clone https://github.com/voglster/lumbergh.git
cd lumbergh
./bootstrap.sh
```

This creates a tmux session with three windows (claude, backend, frontend) and opens `http://localhost:5420` with hot-reloading. You'll need **uv**, **npm**, and **Claude Code** in addition to tmux and git.

The Vite dev server proxies `/api` requests to the backend on port 8420, so the frontend and API appear same-origin during development.

**Tech stack:** Python 3.11+ / FastAPI / libtmux / TinyDB on the backend. React / Vite / TypeScript / xterm.js / Tailwind on the frontend.

Run `./lint.sh` before submitting PRs -- it handles formatting and catches errors.


## Links

- **[Documentation & Screenshots](https://voglster.github.io/lumbergh/)** -- full usage guide, configuration, mobile setup
- [PyPI package](https://pypi.org/project/pylumbergh/)
- [Issues](https://github.com/voglster/lumbergh/issues)
- [Changelog](https://github.com/voglster/lumbergh/releases)

## License

MIT
