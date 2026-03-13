---
title: AI Providers
---

# AI Providers

Lumbergh uses AI for lightweight analysis tasks:

- **Session status detection** -- classifying sessions as `working`, `waiting`, `idle`, or `error`
- **Activity summaries** -- short descriptions of what each session is doing
- **Commit context summaries** -- human-readable summaries of recent changes

Configure your provider in **Settings --> AI**.

!!! tip "Use a fast, cheap model"
    These are short summary tasks, not complex reasoning. A small model like `gpt-4o-mini` or a local Ollama model works great and keeps costs near zero.

## Supported Providers

### Ollama (Local)

Run AI entirely on your machine with no API keys.

| Setting | Default |
|---------|---------|
| Base URL | `http://localhost:11434` |
| Model | `gemma3:latest` |

Models are auto-discovered from your Ollama installation -- any model you've pulled will appear in the dropdown.

### OpenAI

| Setting | Notes |
|---------|-------|
| API Key | Required |
| Models | `gpt-4o` (default), `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo` |

### Anthropic

| Setting | Notes |
|---------|-------|
| API Key | Required |
| Models | Claude Sonnet (default: `claude-sonnet-4-20250514`), Opus, Haiku |

### Google AI

| Setting | Notes |
|---------|-------|
| API Key | Required |
| Models | Gemini Flash (default: `gemini-3-flash-preview`), Gemini Flash Lite |

### OpenAI Compatible

Use any endpoint that implements the OpenAI API format.

| Setting | Notes |
|---------|-------|
| Base URL | Required |
| API Key | Optional (depends on the endpoint) |

This works with local servers like LM Studio, text-generation-webui, or any hosted OpenAI-compatible API.
