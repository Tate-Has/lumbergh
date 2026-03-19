# Commit Message Eval Engines

## What's an Engine?

An engine defines **how** a commit message is generated from a diff. It can be as simple as a prompt change or as complex as a multi-pass pipeline with preprocessing, parallel LLM calls, and structured output parsing.

Each engine produces a single 0-100 score combining:
- **Quality** (1-10): LLM judge rates the generated message against the diff and human reference
- **Speed** (0-2x multiplier): Under 5s is a pass (bonus for faster), over 5s is a zero

## Quick Start

```bash
# Extract the curated eval dataset (one-time)
uv run --project backend python scripts/eval_commits.py extract-curated --repo . -o data/eval-dataset.json

# Run an engine
uv run --project backend python scripts/eval_commits.py eval \
    --engine v1 --dataset data/eval-dataset.json \
    --hosts localhost,10.0.6.44,10.0.6.16

# List engines
uv run --project backend python scripts/eval_commits.py engines

# Compare results
uv run --project backend python scripts/eval_commits.py history

# Detailed results for one run
uv run --project backend python scripts/eval_commits.py report --results data/results/v1.json
```

## Creating a New Engine

1. Copy an existing engine (e.g. `cp engines/v1.py engines/v2.py`)
2. Update the metadata and `generate()` function
3. Run `eval --engine v2`

### Required Interface

```python
# scripts/eval/engines/v2.py

VERSION = "v2"                              # unique version string
DESCRIPTION = "Remove examples from prompt" # what changed
PARENT = "v1"                               # which version this forked from (None for first)

def generate(diff: str, *, base_url: str = "http://localhost:11434") -> str:
    """Generate a commit message from a unified diff.

    Args:
        diff: Raw unified diff string from git
        base_url: Ollama API base URL (for multi-host parallelism)

    Returns:
        The commit message string
    """
    ...
```

### What You Can Change

Engines have full control. Some ideas:

- **Prompt tweaks**: Remove examples that leak into output, restructure instructions, add few-shot examples from the actual diff
- **Preprocessing**: Filter lockfiles, remove generated files, reorder hunks to prioritize source code (see `preprocessing.py`)
- **Structured output**: Use Ollama's `format` parameter with a JSON schema to get structured responses (type, scope, description fields) then assemble the message
- **Multi-pass**: First call to summarize what changed, second call to write the message from the summary
- **Model changes**: Try different models (but watch the 5s speed budget)

### Available Utilities

```python
from .. import ollama_client          # ollama_client.generate(model, prompt, ...)
from ..preprocessing import (
    apply_pipeline,                    # apply named steps + truncate
    filter_lockfiles,                  # remove lockfile hunks
    filter_generated,                  # remove minified/dist hunks
    prioritize_source,                 # reorder: source first, config/docs last
    truncate,                          # truncate to char limit
)
```

## Multi-Host Parallelism

Pass `--hosts localhost,10.0.6.44,10.0.6.16` to distribute work across Ollama instances. Uses work-stealing so faster hosts handle more items. All hosts need the models used by the engine.

## Results

Results auto-save to `data/results/<version>.json`. The `history` command reads all files in that directory and shows a comparison table sorted by score.
