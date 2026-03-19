#!/usr/bin/env python3
"""Commit message eval framework.

Produces a single 0-100 score combining LLM-judged quality and generation speed.
Engines define how commit messages are generated — from simple prompt tweaks
to multi-pass pipelines. Each run is saved with the engine version for comparison.

Usage:
    # One-time: extract dataset
    uv run --project backend python scripts/eval_commits.py extract-curated \\
        --repo . -o data/eval-dataset.json

    # Run eval with an engine (results auto-save to data/results/<version>.json)
    uv run --project backend python scripts/eval_commits.py eval \\
        --dataset data/eval-dataset.json --engine v1

    # List available engines
    uv run --project backend python scripts/eval_commits.py engines

    # Compare all saved results
    uv run --project backend python scripts/eval_commits.py history

    # View one result in detail
    uv run --project backend python scripts/eval_commits.py report \\
        --results data/results/v1.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from eval.dataset import extract_curated, extract_dataset, load_dataset, save_dataset
from eval.engines import list_engines, load_engine
from eval.generator import generate_for_dataset
from eval.judge import judge_dataset
from eval.report import compute_score, format_report, print_report, save_results

RESULTS_DIR = Path("data/results")


def _parse_hosts(args: argparse.Namespace) -> list[str]:
    if args.hosts:
        return [f"http://{h}:11434" for h in args.hosts.split(",")]
    return ["http://localhost:11434"]


def cmd_extract(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    print(f"Extracting up to {args.max_commits} commits from {repo}")
    dataset = extract_dataset(repo, max_commits=args.max_commits, since=args.since)
    print(f"Extracted {len(dataset)} commits")
    save_dataset(dataset, Path(args.output))
    print(f"Saved to {args.output}")


def cmd_extract_curated(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    print(f"Extracting curated eval dataset from {repo}")
    dataset = extract_curated(repo)
    print(f"Extracted {len(dataset)} commits")
    save_dataset(dataset, Path(args.output))
    print(f"Saved to {args.output}")


def cmd_engines(args: argparse.Namespace) -> None:
    engines = list_engines()
    if not engines:
        print("No engines found in scripts/eval/engines/")
        return

    print(f"\n  {'VERSION':<10} {'PARENT':<10} DESCRIPTION")
    print(f"  {'-'*60}")
    for e in engines:
        parent = e["parent"] or "-"
        print(f"  {e['name']:<10} {parent:<10} {e['description']}")
    print()


def cmd_eval(args: argparse.Namespace) -> None:
    engine = load_engine(args.engine)
    dataset = load_dataset(Path(args.dataset))
    base_urls = _parse_hosts(args)

    print(f"Engine:  {engine.VERSION} — {engine.DESCRIPTION}")
    if engine.PARENT:
        print(f"Parent:  {engine.PARENT}")
    print(f"Dataset: {len(dataset)} commits")
    print(f"Judge:   {args.judge_model} (think={'on' if args.judge_think else 'off'})")
    print(f"Hosts:   {', '.join(base_urls)}\n")

    # Generate
    print("Generating...")
    generated = generate_for_dataset(engine, dataset, base_urls=base_urls)

    # Judge
    print("\nJudging...")
    results = judge_dataset(
        dataset,
        generated,
        judge_model=args.judge_model,
        think=args.judge_think,
        max_diff_chars=args.judge_max_diff_chars,
        timeout=args.judge_timeout,
        base_urls=base_urls,
    )

    # Report
    summary = compute_score(results)
    print(f"\n{format_report(results, summary)}")

    # Auto-save to data/results/<version>.json
    output = args.output or str(RESULTS_DIR / f"{engine.VERSION}.json")
    output_path = Path(output)
    save_data = {
        "engine": engine.VERSION,
        "description": engine.DESCRIPTION,
        "parent": getattr(engine, "PARENT", None),
        "judge_model": args.judge_model,
        "judge_think": args.judge_think,
        "summary": summary,
        "results": results,
    }
    save_results(save_data, output_path)
    print(f"\nSaved to {output}")


def cmd_history(args: argparse.Namespace) -> None:
    results_dir = RESULTS_DIR
    if not results_dir.exists():
        print("No results yet. Run an eval first.")
        return

    rows = []
    for f in sorted(results_dir.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)

        if isinstance(data, dict) and "summary" in data:
            s = data["summary"]
            rows.append(
                {
                    "version": data.get("engine", f.stem),
                    "parent": data.get("parent", "-") or "-",
                    "description": data.get("description", ""),
                    "score": s.get("score", 0),
                    "quality": s.get("quality_avg", 0),
                    "speed": s.get("speed_avg", 0),
                    "count": s.get("count", 0),
                }
            )

    if not rows:
        print("No results found.")
        return

    rows.sort(key=lambda r: r["score"], reverse=True)

    print(f"\n  {'VERSION':<10} {'PARENT':<8} {'SCORE':>6} {'QUALITY':>8} {'SPEED':>7}  DESCRIPTION")
    print(f"  {'-'*75}")
    for r in rows:
        print(
            f"  {r['version']:<10} {r['parent']:<8} "
            f"{r['score']:>5.1f} "
            f"{r['quality']:>7.1f}/10 "
            f"{r['speed']:>5.1f}s  "
            f"{r['description'][:40]}"
        )
    print()


def cmd_report(args: argparse.Namespace) -> None:
    path = Path(args.results)
    with open(path) as f:
        data = json.load(f)

    # Handle new format with metadata wrapper
    if isinstance(data, dict) and "results" in data:
        print(f"\n  Engine: {data.get('engine', '?')} — {data.get('description', '')}")
        if data.get("parent"):
            print(f"  Parent: {data['parent']}")
        print(f"  Judge:  {data.get('judge_model', '?')}\n")
        results = data["results"]
    else:
        results = data

    summary = compute_score(results)
    print(format_report(results, summary))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Commit message eval framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    p = sub.add_parser("extract", help="Extract eval dataset from git history")
    p.add_argument("--repo", default=".", help="Path to git repo")
    p.add_argument("--max-commits", type=int, default=50)
    p.add_argument("--since", help="Git --since date filter")
    p.add_argument("-o", "--output", required=True, help="Output JSON path")

    # extract-curated
    p = sub.add_parser("extract-curated", help="Extract curated eval dataset")
    p.add_argument("--repo", default=".", help="Path to git repo")
    p.add_argument("-o", "--output", required=True, help="Output JSON path")

    # engines
    sub.add_parser("engines", help="List available engines")

    # eval
    p = sub.add_parser("eval", help="Run eval with an engine")
    p.add_argument("--engine", required=True, help="Engine version (e.g. v1)")
    p.add_argument("--dataset", required=True, help="Input dataset JSON")
    p.add_argument("--judge-model", default="qwen3.5:9b", help="Judge model")
    p.add_argument("--judge-think", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--judge-max-diff-chars", type=int, default=12000)
    p.add_argument("--judge-timeout", type=float, default=300)
    p.add_argument("--hosts", help="Comma-separated Ollama hosts (e.g. localhost,10.0.6.44,10.0.6.16)")
    p.add_argument("-o", "--output", help="Override output path (default: data/results/<version>.json)")

    # history
    sub.add_parser("history", help="Compare all saved engine results")

    # report
    p = sub.add_parser("report", help="Print detailed results for one run")
    p.add_argument("--results", required=True, help="Results JSON path")

    args = parser.parse_args()
    cmd = {
        "extract": cmd_extract,
        "extract-curated": cmd_extract_curated,
        "engines": cmd_engines,
        "eval": cmd_eval,
        "history": cmd_history,
        "report": cmd_report,
    }
    cmd[args.command](args)


if __name__ == "__main__":
    main()
