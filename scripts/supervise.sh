#!/bin/bash
# Keep a dev server up: if it dies, restart it.
#
# Why: an accidental kill (a stray `pkill -f vite` from an agent in another
# repo, a crash, an OOM) otherwise takes hot reload down silently, and you only
# notice minutes later when the page stops updating. A PreToolUse hook blocks
# the common sweeps; this is the backstop for everything else.
#
# To stop it for real, press Ctrl-C twice: the first interrupt stops the server,
# the second lands in the sleep below and breaks the loop.
set -u

dir="${1:?usage: supervise.sh <dir-containing-start.sh>}"
cd "$dir" || exit 1

while true; do
    ./start.sh
    status=$?
    echo
    echo "[supervise] $dir/start.sh exited ($status) — restarting in 2s. Ctrl-C now to stop."
    sleep 2 || break
done

echo "[supervise] stopped."
