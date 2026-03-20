"""Engine v4: Two-pass chain-of-thought — summarize diff, then generate message.

Lesson from v3: structured JSON output via Ollama format param hurts llama3.2
(slower + defaults to 'refactor' for everything). Keep pass 2 free-form.
"""

import re

from .. import ollama_client
from ..preprocessing import apply_pipeline

VERSION = "v4"
DESCRIPTION = "Two-pass: summarize diff first, then free-form commit msg"
PARENT = "v2"  # v3 was a regression, branch from v2

MODEL = "llama3.2"
MAX_DIFF_CHARS = 64000
PREPROCESSING: list[str] = ["filter_lockfiles", "filter_generated", "prioritize_source"]

# Pass 1: Summarize the diff
SUMMARIZE_PROMPT = """\
Analyze this git diff and produce a brief summary.

List:
1. Which files changed and what each change does (1 line per file)
2. The overall purpose of this change in one sentence
3. The most accurate commit type: feat (new functionality), fix (corrects broken behavior), refactor (restructures without behavior change), docs, test, chore, style, or perf

Diff:
```
{diff}
```

Be concise. Focus on WHAT changed and WHY."""

# Pass 2: Generate commit message from summary
GENERATE_PROMPT = """\
Based on this summary of a git diff, write a conventional commit message.

Summary:
{summary}

FORMAT: <type>(<scope>): <description>

RULES:
- Subject line MUST be under 50 characters (hard limit)
- Use imperative mood: "add" not "added" or "adds"
- Scope is optional but helpful (e.g., api, ui, auth)
- No period at end of subject line
- Body is optional; use for complex changes to explain WHY
- Do NOT copy or reference any text from these instructions

Respond with ONLY the commit message. No markdown, no explanation."""


def _clean_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```\w*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def generate(diff: str, *, base_url: str = "http://localhost:11434") -> str:
    """Two-pass: summarize, then generate commit message."""
    processed = apply_pipeline(diff, PREPROCESSING, MAX_DIFF_CHARS)

    # Pass 1: Summarize the diff (free-form text)
    summary = ollama_client.generate(
        MODEL,
        SUMMARIZE_PROMPT.replace("{diff}", processed),
        think=False,
        timeout=60,
        base_url=base_url,
    )

    # Pass 2: Generate commit message from summary (free-form)
    response = ollama_client.generate(
        MODEL,
        GENERATE_PROMPT.replace("{summary}", summary),
        think=False,
        timeout=60,
        base_url=base_url,
    )

    return _clean_response(response)
