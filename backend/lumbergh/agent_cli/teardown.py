"""`lb teardown` — kill a run's windows and reap its worktrees, refusing unlanded work."""

import os

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

_HELP = _COMMAND_HELP["teardown"]

# What an un-forced teardown refused on, and what actually clears it. "commit+push" was
# the old advice for all of them; under `commit` delivery no worker ever pushes, so it
# named an action nobody takes and left `--force` as the only way through.
_REFUSAL_FIXES = {
    "dirty": "commit or discard the changes",
    "unlanded": "land it with `lb land`",
    "unknown": "check it by hand",
}


def _report_processes(results: list[dict], dry: bool) -> None:
    """Name every leftover, killed or merely doomed: a worker's test server holds a
    port and a shared-DB connection, and a silent kill is its own trap."""
    for r in results:
        for proc in r.get("processes") or []:
            verb = "would kill" if dry else f"killed ({proc.get('signal', 'SIGTERM')})"
            cmd = proc["cmd"]
            _emit(f"{verb}: {r['target']} — {proc['pid']} {cmd[:100]}{'…' * (len(cmd) > 100)}")


def run(flags: dict) -> int:
    if not flags.get("--run"):
        return _err("--run required", _HELP, 2)

    body = {
        "run": flags["--run"],
        "force": "--force" in flags,
        "dry_run": "--dry-run" in flags,
        "caller_pid": os.getpid(),
    }
    resp = _request("POST", "/api/bill/teardown", json=body)
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(
            f"{d.get('stage', 'teardown')}: {d.get('error', 'teardown failed')}", d.get("help"), 1
        )

    d = resp.json()
    header = [("run", d["run"]), ("refused", str(len(d["refused"])))]
    if d.get("dry_run"):
        header.append(("dry run", "nothing was killed or reaped"))
    _emit(render_object(header))
    if d["results"]:
        # `landed: null` is "the check could not run", which renders blank — and blank
        # reads as false to everything downstream. Say the word instead.
        rows = [
            {
                **r,
                "landed": "unknown" if r.get("landed") is None else r["landed"],
                "procs": len(r.get("processes") or []),
            }
            for r in d["results"]
        ]
        _emit(
            render_collection(
                "results", rows, ["target", "killed", "reaped", "landed", "commits", "procs"]
            )
        )

    dry = bool(d.get("dry_run"))
    _report_processes(d["results"], dry)
    # A refused worker is still standing, so nothing happened to its work — saying it
    # "went down unlanded" is the same false alarm this command exists to stop.
    gone = [r for r in d["results"] if dry or r.get("reaped") == "removed"]
    tense = "would go down without landing" if dry else "torn down without landing"

    # Zero commits is the one `landed: false` that lost nothing — everything else,
    # including an unreported count, is work that went down with the worker.
    lost = [r["target"] for r in gone if r.get("landed") is False and r.get("commits") != 0]
    if lost:
        _emit(f"unlanded: {', '.join(lost)} — {tense}; whatever tracks this work is now stale")
    landed_nothing = [r["target"] for r in gone if r.get("commits") == 0]
    if landed_nothing:
        _emit(
            "landed nothing: "
            + ", ".join(landed_nothing)
            + " — no commits to land (a scout's normal ending); nothing was lost"
        )
    unknown = [r["target"] for r in gone if r.get("landed") is None]
    if unknown:
        _emit(
            "landed unknown: "
            + ", ".join(unknown)
            + " — could not tell; do not treat as landed or as lost without looking"
        )
    if d["refused"]:
        _emit(
            "note: "
            + ", ".join(f"{r['target']} ({r.get('reason', 'error')})" for r in d["refused"])
            + " left running — "
            + "; ".join(
                sorted({_REFUSAL_FIXES.get(r.get("reason"), "resolve it") for r in d["refused"]})
            )
            + ", or pass --force"
        )
    return 0
