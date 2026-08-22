"""
Settings router - Global application settings.
Stores settings in ~/.config/lumbergh/settings.json
"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lumbergh import bill as bill_bundle
from lumbergh.db_utils import get_settings_db
from lumbergh.git_identity import DEFAULT_LOOKBACK, DEFAULT_MAX_AGE_DAYS, MAX_LOOKBACK
from lumbergh.providers import DEFAULT_PROVIDER, PROVIDERS

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Database setup
settings_db = get_settings_db()
settings_table = settings_db.table("settings")


def _get_defaults() -> dict:
    """Get default settings, using LUMBERGH_LAUNCH_DIR for repoSearchDir if available."""
    launch_dir = os.environ.get("LUMBERGH_LAUNCH_DIR", "")
    if launch_dir and launch_dir != "/" and Path(launch_dir).exists():
        repo_search_dir = launch_dir
    else:
        repo_search_dir = str(Path.home())

    return {
        "repoSearchDir": repo_search_dir,
        "gitGraphCommits": 100,
        "myEmails": [],
        "mineLookbackCommits": DEFAULT_LOOKBACK,
        "mineMaxBranchAgeDays": DEFAULT_MAX_AGE_DAYS,
        "autoFetchMinutes": 5,
        "defaultAgent": DEFAULT_PROVIDER,
        "bill": {"harness": "pi", "personality": "professional", "customPersonality": ""},
        "tabVisibility": {
            "git": True,
            "files": True,
            "todos": True,
            "prompts": True,
            "shared": True,
        },
        "showSessionDots": True,
        "scratchMaxAgeDays": 7,
        "questionDetectionEnabled": False,
        "cloudUrl": "https://app.lumbergh.dev",
        "ai": {
            # The claude CLI is the out-of-the-box default: anyone running Lumbergh
            # already has Claude Code installed and logged in, so AI features work
            # with no key to paste and no server to install. Existing installs keep
            # whatever provider they already saved.
            "provider": "claude_cli",
            "providers": {
                "claude_cli": {
                    "model": "haiku",
                },
                "ollama": {
                    "baseUrl": "http://localhost:11434",
                    "model": "gemma3:latest",
                },
                "openai": {
                    "apiKey": "",
                    "model": "gpt-4o",
                },
                "anthropic": {
                    "apiKey": "",
                    "model": "claude-sonnet-4-20250514",
                },
                "google": {
                    "apiKey": "",
                    "model": "gemini-3-flash-preview",
                },
                "openai_compatible": {
                    "baseUrl": "",
                    "apiKey": "",
                    "model": "",
                },
                "lumbergh_cloud": {
                    "model": "",
                },
            },
        },
        "worktree": {"base_dir": ""},
    }


class TabVisibility(BaseModel):
    git: bool | None = None
    files: bool | None = None
    todos: bool | None = None
    prompts: bool | None = None
    shared: bool | None = None


class AIProviderConfig(BaseModel):
    baseUrl: str | None = None  # noqa: N815 - API field name
    apiKey: str | None = None  # noqa: N815 - API field name
    model: str | None = None


class AISettings(BaseModel):
    provider: str | None = None
    providers: dict[str, AIProviderConfig] | None = None


class BillSettings(BaseModel):
    personality: str | None = None
    customPersonality: str | None = None  # noqa: N815 - API field name
    harness: str | None = None


class SettingsUpdate(BaseModel):
    repoSearchDir: str | None = None  # noqa: N815 - API field name
    gitGraphCommits: int | None = None  # noqa: N815 - API field name
    myEmails: list[str] | None = None  # noqa: N815 - API field name
    mineLookbackCommits: int | None = None  # noqa: N815 - API field name
    mineMaxBranchAgeDays: int | None = None  # noqa: N815 - API field name
    autoFetchMinutes: int | None = None  # noqa: N815 - API field name
    ai: AISettings | None = None
    defaultAgent: str | None = None  # noqa: N815 - API field name
    tabVisibility: TabVisibility | None = None  # noqa: N815 - API field name
    password: str | None = None
    telemetryConsent: bool | None = None  # noqa: N815 - API field name
    cloudUrl: str | None = None  # noqa: N815 - API field name
    cloudToken: str | None = None  # noqa: N815 - API field name
    cloudUsername: str | None = None  # noqa: N815 - API field name
    backupEnabled: bool | None = None  # noqa: N815 - API field name
    backupIncludeApiKeys: bool | None = None  # noqa: N815 - API field name
    backupPassphrase: str | None = None  # noqa: N815 - API field name
    showSessionDots: bool | None = None  # noqa: N815 - API field name
    scratchMaxAgeDays: int | None = None  # noqa: N815 - API field name
    questionDetectionEnabled: bool | None = None  # noqa: N815 - API field name
    bill: BillSettings | None = None


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dicts. Values in override take precedence.
    Nested dicts are merged recursively.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _ensure_installation_id() -> str:
    """Ensure an installation ID exists in settings, generating one if missing.

    Handles both fresh installs and upgrades from versions without an ID.
    """
    all_settings = settings_table.all()
    if all_settings and all_settings[0].get("installationId"):
        return all_settings[0]["installationId"]

    installation_id = str(uuid.uuid4())
    if all_settings:
        # Upgrade path: patch existing settings

        settings_table.update({"installationId": installation_id}, doc_ids=[all_settings[0].doc_id])
    else:
        # Fresh install: insert with just the ID (defaults merge later)
        settings_table.insert({"installationId": installation_id})
    return installation_id


def get_settings() -> dict:
    """Get current settings, deep merged with defaults."""
    _ensure_installation_id()
    all_settings = settings_table.all()
    stored = all_settings[0] if all_settings else {}
    return deep_merge(_get_defaults(), stored)


def _is_ai_configured(settings: dict) -> bool:
    """Check if the current AI provider has enough config to work."""
    ai = settings.get("ai", {})
    provider = ai.get("provider", "ollama")
    config = ai.get("providers", {}).get(provider, {})

    if provider == "claude_cli":
        return True  # nothing to configure — that is the whole point of it
    if provider == "ollama":
        return bool(config.get("baseUrl"))
    if provider == "openai_compatible":
        return bool(config.get("baseUrl")) and bool(config.get("model"))
    if provider == "lumbergh_cloud":
        return bool(settings.get("cloudToken"))
    # Cloud providers need an API key
    return bool(config.get("apiKey"))


@router.get("")
async def read_settings():
    """Get all settings."""
    settings = get_settings()
    is_first_run = len(settings_table.all()) == 0

    # Don't leak the password value — just report whether auth is configured
    env_pw = os.environ.get("LUMBERGH_PASSWORD", "").strip()
    config_pw = settings.get("password", "").strip()
    password_source = "env" if env_pw else ("config" if config_pw else None)

    # Strip secrets from response
    response = {
        k: v for k, v in settings.items() if k not in ("password", "cloudToken", "backupPassphrase")
    }
    return {
        **response,
        "isFirstRun": is_first_run,
        "aiConfigured": _is_ai_configured(settings),
        "agentProviders": PROVIDERS,
        "passwordSet": bool(env_pw or config_pw),
        "passwordSource": password_source,
    }


def _validate_repo_search_dir(raw: str) -> str:
    """Validate and resolve a repository search directory path."""
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {raw}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {raw}")
    return str(path)


def _validate_mine_filter(updates: SettingsUpdate, update_data: dict[str, object]) -> None:
    """Validate the settings behind the git graph's "just my work" filter."""
    if updates.myEmails is not None:
        update_data["myEmails"] = _normalize_emails(updates.myEmails)

    if updates.mineLookbackCommits is not None:
        if not 1 <= updates.mineLookbackCommits <= MAX_LOOKBACK:
            raise HTTPException(
                status_code=400,
                detail=f"Mine lookback must be between 1 and {MAX_LOOKBACK} commits",
            )
        update_data["mineLookbackCommits"] = updates.mineLookbackCommits

    if updates.mineMaxBranchAgeDays is not None:
        if not 0 <= updates.mineMaxBranchAgeDays <= 3650:
            raise HTTPException(
                status_code=400,
                detail="Branch age cutoff must be between 0 and 3650 days (0 disables it)",
            )
        update_data["mineMaxBranchAgeDays"] = updates.mineMaxBranchAgeDays

    if updates.autoFetchMinutes is not None:
        if not 0 <= updates.autoFetchMinutes <= 1440:
            raise HTTPException(
                status_code=400,
                detail="Auto-fetch interval must be between 0 and 1440 minutes (0 disables it)",
            )
        update_data["autoFetchMinutes"] = updates.autoFetchMinutes


def _normalize_emails(raw: list[str]) -> list[str]:
    """Lowercase, strip and de-duplicate while keeping the order the user typed."""
    seen: dict[str, None] = {}
    for entry in raw:
        email = entry.strip().lower()
        if email:
            seen.setdefault(email, None)
    return list(seen)


_OPTIONAL_FIELDS = (
    "password",
    "telemetryConsent",
    "cloudUrl",
    "cloudToken",
    "cloudUsername",
    "backupEnabled",
    "backupIncludeApiKeys",
    "backupPassphrase",
    "showSessionDots",
    "questionDetectionEnabled",
)


def _copy_optional_fields(updates: SettingsUpdate, update_data: dict[str, object]) -> None:
    """Copy non-None optional fields, stripping strings."""
    for field in _OPTIONAL_FIELDS:
        val = getattr(updates, field)
        if val is not None:
            update_data[field] = val.strip() if isinstance(val, str) else val


def _validate_updates(updates: SettingsUpdate) -> dict[str, object]:
    """Validate and extract update data from a settings update request."""
    update_data: dict[str, object] = {}

    if updates.repoSearchDir is not None:
        update_data["repoSearchDir"] = _validate_repo_search_dir(updates.repoSearchDir)

    if updates.gitGraphCommits is not None:
        if updates.gitGraphCommits < 10 or updates.gitGraphCommits > 1000:
            raise HTTPException(
                status_code=400,
                detail="Git graph commits must be between 10 and 1000",
            )
        update_data["gitGraphCommits"] = updates.gitGraphCommits

    _validate_mine_filter(updates, update_data)

    if updates.defaultAgent is not None:
        if updates.defaultAgent not in PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent provider: {updates.defaultAgent}",
            )
        update_data["defaultAgent"] = updates.defaultAgent

    if updates.tabVisibility is not None:
        tv = updates.tabVisibility.model_dump(exclude_none=True)
        # Merge with current to check at least one tab stays visible
        current_tv = get_settings().get("tabVisibility", {})
        merged_tv = {**current_tv, **tv}
        if not any(merged_tv.values()):
            raise HTTPException(
                status_code=400,
                detail="At least one tab must remain visible",
            )
        update_data["tabVisibility"] = tv

    _copy_optional_fields(updates, update_data)

    if updates.ai is not None:
        update_data["ai"] = _serialize_ai_update(updates.ai)

    if updates.bill is not None:
        update_data["bill"] = _validate_bill_update(updates.bill)

    return update_data


_MAX_CUSTOM_PERSONALITY = 4000


def _validate_bill_update(bill: BillSettings) -> dict:
    """Extract the provided Bill fields, rejecting an unknown personality/harness or an
    over-long custom personality. Only set fields are returned, so a partial update
    deep-merges cleanly over the stored block."""
    data = bill.model_dump(exclude_none=True)

    if "personality" in data:
        valid = set(bill_bundle.available_personalities()) | {bill_bundle.CUSTOM_PERSONALITY}
        if data["personality"] not in valid:
            raise HTTPException(
                status_code=400, detail=f"Unknown personality: {data['personality']}"
            )

    if "harness" in data and data["harness"] not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown agent provider: {data['harness']}")

    if "customPersonality" in data and len(data["customPersonality"]) > _MAX_CUSTOM_PERSONALITY:
        raise HTTPException(
            status_code=400,
            detail=f"Custom personality must be at most {_MAX_CUSTOM_PERSONALITY} characters",
        )

    return data


def _serialize_ai_update(ai: AISettings) -> dict:
    """Convert AI settings update to a plain dict."""
    ai_update = ai.model_dump(exclude_none=True)
    if "providers" in ai_update:
        ai_update["providers"] = {
            k: v.model_dump(exclude_none=True) if hasattr(v, "model_dump") else v
            for k, v in ai_update["providers"].items()
        }
    return ai_update


@router.patch("")
async def update_settings(updates: SettingsUpdate):
    """Update settings. Only provided fields are updated."""
    update_data = _validate_updates(updates)

    current = get_settings()
    merged = deep_merge(current, update_data)

    settings_table.truncate()
    settings_table.insert(merged)

    return get_settings()
