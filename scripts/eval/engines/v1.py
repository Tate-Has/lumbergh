"""Engine v1: Baseline — raw diff stuffed into conventional commits prompt."""

import re
import time

from .. import ollama_client
from ..preprocessing import apply_pipeline

VERSION = "v1"
DESCRIPTION = "Baseline: raw diff → conventional commits prompt → llama3.2"
PARENT = None  # first version

MODEL = "llama3.2"
MAX_DIFF_CHARS = 8000
PREPROCESSING: list[str] = []

PROMPT = """\
Generate a git commit message following the Conventional Commits specification.

FORMAT:
<type>(<scope>): <description>

[optional body]

TYPES (pick one):
- feat: new feature or capability
- fix: bug fix
- refactor: code change that neither fixes a bug nor adds a feature
- docs: documentation only
- test: adding or updating tests
- chore: maintenance tasks (deps, config, build)
- style: formatting, whitespace (no logic change)
- perf: performance improvement

RULES:
- Subject line MUST be under 50 characters (hard limit)
- Use imperative mood: "add" not "added" or "adds"
- Scope is optional but helpful (e.g., api, ui, auth)
- No period at end of subject line
- Body is optional; use for complex changes to explain WHY

EXAMPLES:
- feat(ai): add commit message generation
- fix: prevent crash on empty diff
- refactor(providers): extract base class for AI providers
- chore: update dependencies

Diff:
```
{diff}
```

Respond with ONLY the commit message. No markdown, no explanation."""


def _clean_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```\w*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def generate(diff: str, *, base_url: str = "http://localhost:11434") -> str:
    """Generate a commit message from a diff."""
    processed = apply_pipeline(diff, PREPROCESSING, MAX_DIFF_CHARS)
    prompt = PROMPT.replace("{diff}", processed)

    response = ollama_client.generate(
        MODEL,
        prompt,
        think=False,
        timeout=120,
        base_url=base_url,
    )
    return _clean_response(response)
