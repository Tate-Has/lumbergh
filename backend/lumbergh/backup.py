"""
Backup data collection and restoration logic.

Reads local TinyDB JSON files and shared markdown files, strips secrets,
optionally encrypts, and prepares data for cloud upload. Also handles
restoring backup data to local files.
"""

import hashlib
import json
import logging
import os
import platform
from pathlib import Path

from lumbergh.constants import CONFIG_DIR, PROJECTS_DIR, SESSIONS_DATA_DIR, SHARED_DIR

logger = logging.getLogger(__name__)

# Settings keys that are always stripped from backups (machine-specific or secret)
_ALWAYS_STRIP = {"password", "cloudToken", "cloudUrl", "installationId"}

# Settings keys stripped unless user opts in to including API keys
_API_KEY_PATHS = {"ai"}


def _read_json_file(path: Path) -> dict | None:
    """Read a JSON file, returning None if missing or invalid."""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _write_json_file(path: Path, data: dict) -> None:
    """Write a dict as JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def _strip_settings(settings_data: dict, include_api_keys: bool) -> dict:
    """Strip secrets from settings data."""
    result = {k: v for k, v in settings_data.items() if k not in _ALWAYS_STRIP}
    if not include_api_keys:
        result.pop("ai", None)
    return result


def _collect_json_dir(directory: Path, use_stem: bool = True) -> dict:
    """Collect all JSON files from a directory into a dict keyed by filename."""
    result = {}
    if directory.is_dir():
        for f in directory.glob("*.json"):
            content = _read_json_file(f)
            if content:
                result[f.stem if use_stem else f.name] = content
    return result


def _collect_shared_md() -> dict:
    """Collect all markdown files from the shared directory."""
    result = {}
    if SHARED_DIR.is_dir():
        for f in SHARED_DIR.glob("*.md"):
            try:
                result[f.name] = f.read_text()
            except OSError:
                pass
    return result


def collect_backup_data(include_api_keys: bool = False) -> dict:
    """Collect all local data for backup.

    Returns a dict matching the cloud backup schema's `data` field.
    """
    data: dict = {}

    # Top-level JSON files
    for filename, key in [
        ("settings.json", "settings"),
        ("sessions.json", "sessions"),
        ("global.json", "global"),
    ]:
        content = _read_json_file(CONFIG_DIR / filename)
        if content:
            data[key] = _strip_settings(content, include_api_keys) if key == "settings" else content

    # Directory-based collections
    for directory, key in [(PROJECTS_DIR, "projects"), (SESSIONS_DATA_DIR, "session_data")]:
        collected = _collect_json_dir(directory)
        if collected:
            data[key] = collected

    shared_md = _collect_shared_md()
    if shared_md:
        data["shared_md"] = shared_md

    return data


def compute_data_hash(data: dict) -> str:
    """Compute MD5 hash of serialized backup data for change detection."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()


def get_backup_meta(data: dict) -> dict:
    """Build metadata dict for the backup."""
    try:
        from lumbergh._version import __version__
    except ImportError:
        __version__ = "unknown"

    file_count = sum(
        1 for key in data if key not in ("projects", "session_data", "shared_md")
    ) + sum(
        len(v)
        for key, v in data.items()
        if key in ("projects", "session_data", "shared_md") and isinstance(v, dict)
    )

    return {
        "lumbergh_version": __version__,
        "os": platform.system(),
        "hostname": platform.node(),
        "file_count": file_count,
        "data_hash": compute_data_hash(data),
    }


def encrypt_data(data: dict, passphrase: str) -> str:
    """AES-256-GCM encrypt backup data with a passphrase-derived key.

    Returns a base64-encoded string containing salt + nonce + ciphertext + tag.
    """
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    salt = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    key = kdf.derive(passphrase.encode())

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    plaintext = json.dumps(data, default=str).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Pack: salt(16) + nonce(12) + ciphertext+tag
    return base64.b64encode(salt + nonce + ciphertext).decode()


def decrypt_data(ciphertext_b64: str, passphrase: str) -> dict:
    """Decrypt AES-256-GCM encrypted backup data.

    Raises ValueError on wrong passphrase or corrupt data.
    """
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    try:
        raw = base64.b64decode(ciphertext_b64)
    except Exception as exc:
        raise ValueError("Invalid backup data") from exc

    if len(raw) < 28:  # 16 salt + 12 nonce
        raise ValueError("Invalid backup data")

    salt = raw[:16]
    nonce = raw[16:28]
    ciphertext = raw[28:]

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    key = kdf.derive(passphrase.encode())

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError("Wrong passphrase or corrupt data") from exc

    return json.loads(plaintext)


def _restore_settings(settings_data: dict) -> None:
    """Restore settings, preserving local-only fields."""
    existing = _read_json_file(CONFIG_DIR / "settings.json") or {}
    restored = settings_data.copy()
    for key in _ALWAYS_STRIP:
        if key in existing:
            restored[key] = existing[key]
    _write_json_file(CONFIG_DIR / "settings.json", restored)


def _restore_json_dir(directory: Path, items: dict) -> None:
    """Restore a dict of JSON files into a directory."""
    for name, content in items.items():
        _write_json_file(directory / f"{name}.json", content)


def apply_backup_data(data: dict) -> None:
    """Write backup data to local files, preserving local-only settings."""
    if "settings" in data:
        _restore_settings(data["settings"])

    for key, filename in [("sessions", "sessions.json"), ("global", "global.json")]:
        if key in data:
            _write_json_file(CONFIG_DIR / filename, data[key])

    for key, directory in [("projects", PROJECTS_DIR), ("session_data", SESSIONS_DATA_DIR)]:
        if key in data:
            _restore_json_dir(directory, data[key])

    if "shared_md" in data:
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        for filename, content in data["shared_md"].items():
            (SHARED_DIR / filename).write_text(content)
