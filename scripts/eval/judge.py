"""LLM-as-judge: single 1-10 quality score with JSON schema enforcement."""

import json

from . import ollama_client

JUDGE_SYSTEM = """You are an expert code reviewer evaluating git commit messages.

Score the candidate commit message from 1 to 10 based on:
- Does it correctly describe what changed? Is the type (feat/fix/refactor/etc.) correct?
- Does it capture the significant changes?
- Is it appropriately concise?
- Does it follow conventional commits format?
- Does it use specific domain terms rather than vague language like "update code"?

10 = perfectly describes the commit. 1 = completely wrong or useless.

You MUST respond with JSON: {"score": N, "reason": "brief explanation"}"""

JUDGE_PROMPT = """## Diff
```
{diff}
```

## Human-written message (reference)
{human_message}

## Candidate message to score
{candidate_message}"""

# JSON schema for structured output enforcement
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 10},
        "reason": {"type": "string"},
    },
    "required": ["score", "reason"],
}


def _parse_score(response: str) -> tuple[int, str]:
    """Extract score and reason from judge response."""
    data = json.loads(response)
    score = data["score"]
    if not isinstance(score, (int, float)) or not (1 <= score <= 10):
        raise ValueError(f"Invalid score: {score}")
    return int(score), data.get("reason", "")


def judge_message(
    diff: str,
    human_message: str,
    candidate_message: str,
    *,
    judge_model: str = "qwen3.5:35b",
    think: bool = True,
    max_diff_chars: int = 12000,
    timeout: float = 300,
    base_url: str = "http://localhost:11434",
) -> tuple[int, str]:
    """Score a candidate commit message 1-10.

    Returns (score, reason).
    """
    truncated_diff = diff[:max_diff_chars]
    if len(diff) > max_diff_chars:
        truncated_diff += "\n... [truncated]"

    prompt = JUDGE_PROMPT.format(
        diff=truncated_diff,
        human_message=human_message,
        candidate_message=candidate_message,
    )

    response = ollama_client.generate(
        judge_model,
        prompt,
        system=JUDGE_SYSTEM,
        think=think,
        format=SCORE_SCHEMA,
        timeout=timeout,
        base_url=base_url,
    )

    return _parse_score(response)


def _judge_one(
    entry: dict,
    gen: dict,
    index: int,
    total: int,
    *,
    judge_model: str,
    think: bool,
    max_diff_chars: int,
    timeout: float,
    base_url: str,
) -> dict:
    """Judge a single entry. Thread-safe."""
    sha = entry["sha"]
    label = f"  [{index + 1}/{total}] {sha[:8]}..."

    try:
        quality, reason = judge_message(
            entry["diff"],
            entry["original_message"],
            gen["generated_message"],
            judge_model=judge_model,
            think=think,
            max_diff_chars=max_diff_chars,
            timeout=timeout,
            base_url=base_url,
        )

        ss = gen["speed_score"]
        composite = quality * ss if ss > 0 else 0.0

        print(f"{label} q={quality}/10 t={gen['elapsed']:.1f}s | {reason[:60]}", flush=True)

        return {
            **gen,
            "original_message": entry["original_message"],
            "quality": quality,
            "reason": reason,
            "composite": round(composite, 2),
        }
    except Exception as e:
        print(f"{label} ERROR: {e}", flush=True)
        return {
            **gen,
            "original_message": entry["original_message"],
            "error": str(e),
        }


def judge_dataset(
    dataset: list[dict],
    generated: list[dict],
    *,
    judge_model: str = "qwen3.5:9b",
    think: bool = True,
    max_diff_chars: int = 12000,
    timeout: float = 300,
    base_urls: list[str] | None = None,
) -> list[dict]:
    """Judge all entries. Returns list with quality scores added.

    When multiple base_urls are provided, distributes judging across hosts.
    """
    if not base_urls:
        base_urls = ["http://localhost:11434"]

    gen_by_sha = {g["sha"]: g for g in generated}

    # Build work items
    work = []
    for i, entry in enumerate(dataset):
        gen = gen_by_sha.get(entry["sha"])
        if gen:
            work.append((entry, gen, i))

    if len(base_urls) == 1:
        return [
            _judge_one(
                entry, gen, idx, len(dataset),
                judge_model=judge_model, think=think,
                max_diff_chars=max_diff_chars, timeout=timeout,
                base_url=base_urls[0],
            )
            for entry, gen, idx in work
        ]

    # Multi-host: work-stealing via queue so faster hosts take more work
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from queue import Queue

    work_queue: Queue[tuple[dict, dict, int]] = Queue()
    for item in work:
        work_queue.put(item)

    results_by_sha: dict[str, dict] = {}

    def worker(host: str) -> None:
        while not work_queue.empty():
            try:
                entry, gen, idx = work_queue.get_nowait()
            except Exception:
                break
            result = _judge_one(
                entry, gen, idx, len(dataset),
                judge_model=judge_model, think=think,
                max_diff_chars=max_diff_chars, timeout=timeout,
                base_url=host,
            )
            results_by_sha[result["sha"]] = result

    with ThreadPoolExecutor(max_workers=len(base_urls)) as pool:
        futures = [pool.submit(worker, host) for host in base_urls]
        for fut in as_completed(futures):
            fut.result()

    return [results_by_sha[entry["sha"]] for entry, _, _ in work]
