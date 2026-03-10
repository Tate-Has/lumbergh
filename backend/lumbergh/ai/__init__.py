"""
AI module for Lumbergh.

Provides provider-agnostic AI completions with support for:
- Ollama (local)
- OpenAI
- Anthropic
- OpenAI-compatible endpoints
"""

from lumbergh.ai.prompts import DEFAULT_COMMIT_MESSAGE_PROMPT, get_ai_prompt
from lumbergh.ai.providers import AIProvider, get_provider

__all__ = ["DEFAULT_COMMIT_MESSAGE_PROMPT", "AIProvider", "get_ai_prompt", "get_provider"]
