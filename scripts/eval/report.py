"""Report: single 0-100 normalized score."""

import json
from pathlib import Path

from .generator import TIME_BUDGET


def compute_score(results: list[dict]) -> dict:
    """Compute a single 0-100 score from eval results.

    Formula: mean(quality * speed_score) normalized to 0-100.
    Speed score: 0 if >5s, 1.0 at 5s, max 2.0 at ≤2.5s.
    Max composite per entry = 10 * 2.0 = 20.
    """
    max_composite = 10.0 * 2.0  # 10 quality * 2.0 max speed_score = 20

    composites = []
    errors = 0
    speed_fails = 0

    for r in results:
        if "error" in r:
            errors += 1
            composites.append(0.0)
            continue
        if r["speed_score"] == 0:
            speed_fails += 1
        composites.append(r["composite"])

    if not composites:
        return {"score": 0, "count": 0, "errors": errors}

    raw_mean = sum(composites) / len(composites)
    # Normalize to 0-100, capped at 100
    score = min(100.0, (raw_mean / max_composite) * 100)

    # Also compute quality-only and speed-only averages for detail
    scored = [r for r in results if "error" not in r]
    avg_quality = sum(r["quality"] for r in scored) / len(scored) if scored else 0
    avg_speed = sum(r["elapsed"] for r in scored) / len(scored) if scored else 0

    return {
        "score": round(score, 1),
        "quality_avg": round(avg_quality, 1),
        "speed_avg": round(avg_speed, 2),
        "count": len(composites),
        "errors": errors,
        "speed_fails": speed_fails,
    }


def format_report(results: list[dict], summary: dict | None = None) -> str:
    """Format a human-readable report with a single score."""
    if summary is None:
        summary = compute_score(results)

    if summary["count"] == 0:
        return "No results to report."

    lines = []
    lines.append(f"  Score: {summary['score']}/100")
    lines.append(f"")
    lines.append(
        f"  {summary['count']} commits | "
        f"quality {summary['quality_avg']}/10 | "
        f"speed {summary['speed_avg']:.1f}s avg | "
        f"{summary['errors']} errors | "
        f"{summary['speed_fails']} too slow"
    )

    # Worst entries
    scored = [r for r in results if "error" not in r]
    worst = sorted(scored, key=lambda r: r["composite"])[:3]
    if worst:
        lines.append(f"\n  Worst:")
        for r in worst:
            msg = r["generated_message"].splitlines()[0][:45]
            reason = r.get("reason", "")[:40]
            lines.append(
                f"    {r['sha'][:8]} q={r['quality']:>2} {r['elapsed']:.1f}s | {msg}"
            )
            if reason:
                lines.append(f"             {reason}")

    return "\n".join(lines)


def print_report(results_path: Path) -> None:
    """Load results JSON and print report."""
    with open(results_path) as f:
        data = json.load(f)

    if isinstance(data, list):
        summary = compute_score(data)
        print(f"\n{format_report(data, summary)}\n")
    elif isinstance(data, dict) and "candidates" in data:
        rows = []
        for name, entries in data["candidates"].items():
            s = compute_score(entries)
            rows.append((name, s, entries))
        rows.sort(key=lambda r: r[1]["score"], reverse=True)

        for name, s, entries in rows:
            print(f"\n  {name}: {s['score']}/100")
            print(format_report(entries, s))
        print()
    else:
        print("Unknown results format")


def save_results(results: list[dict] | dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
