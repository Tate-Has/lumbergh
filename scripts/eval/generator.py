"""Generate commit messages via engine modules, with timing and scoring."""

import time
from types import ModuleType

TIME_BUDGET = 7.0  # seconds — over this is a fail


def speed_score(elapsed: float) -> float:
    """Compute speed score. 0 if over budget, 1.0 at budget, max 2.0.

    Linear scale: 5s->1.0, 2.5s->2.0, <2.5s->2.0 (capped).
    Over 5s->0 (fail).
    """
    if elapsed <= 0 or elapsed > TIME_BUDGET:
        return 0.0
    return min(2.0, TIME_BUDGET / elapsed)


def _generate_one(
    engine: ModuleType,
    entry: dict,
    index: int,
    total: int,
    *,
    base_url: str,
) -> dict:
    """Generate for a single entry using the engine. Thread-safe."""
    label = f"  [{index + 1}/{total}] {entry['sha'][:8]}..."
    try:
        start = time.monotonic()
        msg = engine.generate(entry["diff"], base_url=base_url)
        elapsed = time.monotonic() - start

        ss = speed_score(elapsed)
        status = "FAIL" if ss == 0 else f"{ss:.1f}x"
        print(f"{label} {elapsed:.1f}s [{status}] {msg.splitlines()[0][:50]}", flush=True)
    except Exception as e:
        msg = f"[ERROR: {e}]"
        elapsed = 0.0
        print(f"{label} ERROR: {e}", flush=True)

    return {
        "sha": entry["sha"],
        "generated_message": msg,
        "elapsed": round(elapsed, 2),
        "speed_score": round(speed_score(elapsed), 2),
    }


def generate_for_dataset(
    engine: ModuleType,
    dataset: list[dict],
    *,
    base_urls: list[str] | None = None,
) -> list[dict]:
    """Generate messages for all entries using the given engine.

    When multiple base_urls are provided, uses work-stealing parallelism
    so faster hosts handle more work.
    """
    if not base_urls:
        base_urls = ["http://localhost:11434"]

    if len(base_urls) == 1:
        return [
            _generate_one(engine, entry, i, len(dataset), base_url=base_urls[0])
            for i, entry in enumerate(dataset)
        ]

    # Multi-host: work-stealing via queue
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from queue import Queue

    work_queue: Queue[tuple[int, dict]] = Queue()
    for i, entry in enumerate(dataset):
        work_queue.put((i, entry))

    results_by_sha: dict[str, dict] = {}

    def worker(host: str) -> None:
        while not work_queue.empty():
            try:
                i, entry = work_queue.get_nowait()
            except Exception:
                break
            result = _generate_one(engine, entry, i, len(dataset), base_url=host)
            results_by_sha[result["sha"]] = result

    with ThreadPoolExecutor(max_workers=len(base_urls)) as pool:
        futures = [pool.submit(worker, host) for host in base_urls]
        for fut in as_completed(futures):
            fut.result()

    return [results_by_sha[entry["sha"]] for entry in dataset]
