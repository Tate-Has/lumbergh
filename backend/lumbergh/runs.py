"""Query the registry for the members of a run group."""

from lumbergh import worktrees


def run_members(run_id: str) -> list[dict]:
    rows = [r for r in worktrees.all_entries() if r.get("run") == run_id]
    return sorted(rows, key=lambda r: r.get("target") or "")


def normalize(run: str | list[str]) -> list[str]:
    """The run ids a command was given, in the caller's order and without repeats.

    Order is preserved because it is the cherry-pick order of the assembly, so
    ``--run a --run b`` and ``--run b --run a`` are different builds, not the same one
    spelled twice.
    """
    ids = [run] if isinstance(run, str) else list(run)
    return list(dict.fromkeys(i for i in ids if i))


def batch_branch(run_ids: list[str]) -> str:
    """The branch a land of exactly this run set assembles onto.

    One run keeps its historical ``batch-<run>`` name. A multi-run land names every run
    it covers, so the batch branch and the teardown that drops it agree on identity
    without either side having to remember which runs were combined.
    """
    return "batch-" + "+".join(run_ids)


def group_members(run_ids: list[str], lookup=run_members) -> tuple[list[dict], list[str]]:
    """Every member of every named run, plus the run ids that had none.

    Empty runs come back named rather than folded into the members: landing four runs
    when one of them was a typo must not look identical to landing three.
    """
    members, empty = [], []
    for run_id in run_ids:
        found = lookup(run_id)
        members.extend(found) if found else empty.append(run_id)
    return members, empty
