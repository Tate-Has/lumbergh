"""
AI provider abstraction layer.

Supports multiple AI backends with a unified interface.
"""

import asyncio
import shutil
from abc import ABC, abstractmethod
from typing import Any

import httpx


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Generate a completion for the given prompt."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...


class OllamaProvider(AIProvider):
    """Ollama local LLM provider."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()["response"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models from Ollama."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [
                {
                    "name": m["name"],
                    "size": m.get("size", 0),
                    "parameter_size": m.get("details", {}).get("parameter_size", ""),
                }
                for m in data.get("models", [])
            ]


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def complete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception:
            return False


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    async def complete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]

    async def health_check(self) -> bool:
        # Anthropic doesn't have a simple health endpoint, so just check if key exists
        return bool(self.api_key)


class GoogleAIProvider(AIProvider):
    """Google AI (Gemini) API provider."""

    def __init__(self, api_key: str, model: str = "gemini-3-flash-preview"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def complete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}},
                },
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def health_check(self) -> bool:
        # Google AI doesn't have a simple health endpoint, so just check if key exists
        return bool(self.api_key)


class LumberghCloudProvider(AIProvider):
    """Lumbergh Cloud AI provider — proxies through lumbergh-cloud to LiteLLM."""

    def __init__(self, model: str = "llama3.2", **_kwargs):
        self.model = model

    async def complete(self, prompt: str) -> str:
        from lumbergh import cloud_client

        response = await cloud_client.request(
            "POST",
            "/api/ai/v1/chat/completions",
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        from lumbergh import cloud_client

        try:
            response = await cloud_client.request(
                "GET",
                "/api/ai/v1/models",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models from Lumbergh Cloud."""
        from lumbergh import cloud_client

        response = await cloud_client.request(
            "GET",
            "/api/ai/v1/models",
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        return [{"name": m["id"]} for m in data.get("data", [])]


class ClaudeCliProvider(AIProvider):
    """The `claude` CLI in one-shot mode.

    Anyone running Lumbergh already has Claude Code installed and logged in, so
    this is the provider that needs no API key and no configuration. Tools and
    MCP servers are switched off: these prompts summarize text, and an agent
    that can read files or run commands would be slower and less predictable
    for no benefit.
    """

    def __init__(self, model: str = "haiku", timeout: float = 60.0):
        self.model = model
        self.timeout = timeout

    def _command(self, prompt: str) -> list[str]:
        return [
            "claude",
            "-p",
            prompt,
            "--model",
            self.model,
            "--allowed-tools",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
        ]

    async def complete(self, prompt: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command(prompt),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as e:
            raise RuntimeError(f"Could not run the claude CLI: {e}") from e

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
        except TimeoutError as e:
            process.kill()
            raise RuntimeError(f"claude timed out after {self.timeout}s") from e

        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip() or "no output"
            raise RuntimeError(f"claude exited {process.returncode}: {detail[:300]}")
        return stdout.decode(errors="replace").strip()

    async def health_check(self) -> bool:
        if shutil.which("claude") is None:
            return False
        try:
            process = await asyncio.create_subprocess_exec(
                "claude",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=10.0)
        except (OSError, TimeoutError):
            return False
        return True


class OpenAICompatibleProvider(AIProvider):
    """OpenAI-compatible API provider (e.g., local vLLM, text-generation-inference)."""

    def __init__(self, base_url: str, api_key: str = "", model: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/models", headers=headers)
                return response.status_code == 200
        except Exception:
            return False


def get_provider(ai_settings: dict, settings: dict | None = None) -> AIProvider:  # noqa: ARG001
    """
    Factory function to get the appropriate AI provider based on settings.

    Args:
        ai_settings: The 'ai' section of the settings dict, containing:
            - provider: str (ollama, openai, anthropic, openai_compatible, lumbergh_cloud)
            - providers: dict with provider-specific settings
        settings: Deprecated — kept for caller compat, no longer used.

    Returns:
        An AIProvider instance
    """
    provider_name = ai_settings.get("provider", "ollama")
    providers_config = ai_settings.get("providers", {})
    config = providers_config.get(provider_name, {})

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=config.get("baseUrl", "http://localhost:11434"),
            model=config.get("model", "llama3.2"),
        )
    if provider_name == "openai":
        return OpenAIProvider(
            api_key=config.get("apiKey", ""),
            model=config.get("model", "gpt-4o"),
        )
    if provider_name == "anthropic":
        return AnthropicProvider(
            api_key=config.get("apiKey", ""),
            model=config.get("model", "claude-sonnet-4-20250514"),
        )
    if provider_name == "google":
        return GoogleAIProvider(
            api_key=config.get("apiKey", ""),
            model=config.get("model", "gemini-3-flash-preview"),
        )
    if provider_name == "claude_cli":
        return ClaudeCliProvider(model=config.get("model") or "haiku")
    if provider_name == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=config.get("baseUrl", ""),
            api_key=config.get("apiKey", ""),
            model=config.get("model", "default"),
        )
    if provider_name == "lumbergh_cloud":
        return LumberghCloudProvider(
            model=config.get("model") or "llama3.2",
        )
    raise ValueError(f"Unknown AI provider: {provider_name}")
