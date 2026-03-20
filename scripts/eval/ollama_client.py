"""Sync Ollama HTTP client for eval scripts."""

import httpx


def generate(
    model: str,
    prompt: str,
    *,
    system: str | None = None,
    think: bool = False,
    format: dict | str | None = None,
    temperature: float | None = None,
    timeout: float = 120,
    base_url: str = "http://localhost:11434",
) -> str:
    """Call Ollama /api/chat and return the response text.

    Args:
        format: "json" for free-form JSON, or a JSON schema dict for
                structured output enforcement.
        think: Enable extended thinking (qwen3.5, etc.).
        temperature: Sampling temperature (0.0 = deterministic).
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
    }
    if format is not None:
        payload["format"] = format
    if temperature is not None:
        payload.setdefault("options", {})["temperature"] = temperature

    resp = httpx.post(
        f"{base_url}/api/chat",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]
