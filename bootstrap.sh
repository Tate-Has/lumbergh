#!/bin/bash
# Bootstrap lumbergh: tmux session lumbergh with claude, backend, and frontend
# Then open the browser and exit.

cd "$(dirname "$0")"

# Opening a browser is the right default for a human running this by hand, but
# wrong for an automated start (systemd user unit, login hook) where it would
# pop a tab on every boot. --no-browser (or LUMBERGH_NO_BROWSER=1) opts out.
open_browser=true
for arg in "$@"; do
    case "$arg" in
        --no-browser) open_browser=false ;;
        -h|--help)
            echo "usage: bootstrap.sh [--no-browser]"
            echo "  --no-browser   start the session but don't open a browser tab"
            echo "                 (also honours LUMBERGH_NO_BROWSER=1)"
            exit 0
            ;;
        *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done
[ -n "${LUMBERGH_NO_BROWSER:-}" ] && open_browser=false

# Check required dependencies
has_missing=false
for cmd in tmux git uv node; do
    if ! command -v "$cmd" &>/dev/null; then
        has_missing=true
        echo "Missing: $cmd"
        case "$cmd" in
            tmux)
                echo "  Install: sudo apt install tmux  (or: brew install tmux)"
                ;;
            git)
                echo "  Install: sudo apt install git  (or: brew install git)"
                ;;
            uv)
                echo "  Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
                echo "  More info: https://docs.astral.sh/uv/"
                ;;
            node)
                echo "  Recommended: install via nvm (Node Version Manager)"
                echo "  Install nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
                echo "  Then: nvm install --lts"
                echo "  More info: https://github.com/nvm-sh/nvm"
                ;;
        esac
        echo ""
    fi
done
if [ "$has_missing" = true ]; then
    echo "Install the missing tools above, then open a new shell (or run: source ~/.bashrc)"
    echo "and re-run this script."
    exit 1
fi

# Check Node.js version meets minimum requirements
source "$(dirname "$0")/scripts/check-node.sh"

if tmux has-session -t lumbergh 2>/dev/null; then
    echo "Session 'lumbergh' already exists. Attach with: tmux at -t lumbergh"
    exit 1
fi

# Window 0: claude
tmux new-session -d -s lumbergh -n claude
tmux send-keys -t lumbergh:claude "claude --continue 2>/dev/null || claude" Enter

# Window 1: backend
tmux new-window -t lumbergh: -n backend
tmux send-keys -t lumbergh:backend "$(pwd)/scripts/supervise.sh $(pwd)/backend" Enter

# Window 2: frontend
tmux new-window -t lumbergh: -n frontend
tmux send-keys -t lumbergh:frontend "$(pwd)/scripts/supervise.sh $(pwd)/frontend" Enter

# Make `lb` (the agent control CLI) available to agent sessions when running from
# source. A `uv tool install pylumbergh` already puts `lb` on PATH, so this is a
# no-op in that case.
if ! command -v lb &>/dev/null; then
    mkdir -p "$HOME/.local/bin"
    cat > "$HOME/.local/bin/lb" <<EOF
#!/bin/bash
exec "$(pwd)/backend/.venv/bin/python" -m lumbergh.agent_cli.main "\$@"
EOF
    chmod +x "$HOME/.local/bin/lb"
    echo "Installed 'lb' agent CLI shim at ~/.local/bin/lb (ensure ~/.local/bin is on PATH)"
fi

# Seed Lumbergh's agent skills (lb for coordinators, ship/scout for workers) into every
# present agent skills dir, so spawned pi/claude workers pick them up. Idempotent.
"$(pwd)/backend/.venv/bin/python" -m lumbergh.agent_cli.main skill install >/dev/null 2>&1 \
    && echo "Seeded Lumbergh agent skills (lb, ship, scout)"

# Ensure tmux mouse mode is on (required for xterm.js terminal interaction)
if [ "$(tmux show-option -gv mouse 2>/dev/null)" != "on" ]; then
    tmux set -g mouse on
    echo "Enabled tmux mouse mode (needed for browser terminals)"
    echo "Tip: install a full tmux config from the Lumbergh dashboard for persistence"
fi

# Select the claude window
tmux select-window -t lumbergh:claude

# Give the frontend a moment to start, then open browser
if [ "$open_browser" = true ]; then
    sleep 2
    xdg-open http://localhost:5420 2>/dev/null || open http://localhost:5420 2>/dev/null
fi

echo "Lumbergh bootstrapped in tmux session 'lumbergh'"
