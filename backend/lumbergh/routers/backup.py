"""
Backup proxy router — local endpoints that orchestrate cloud backup operations.
"""

import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lumbergh.backup import (
    apply_backup_data,
    collect_backup_data,
    compute_data_hash,
    decrypt_data,
    encrypt_data,
    get_backup_meta,
)
from lumbergh.routers.settings import deep_merge, get_settings, settings_table

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _get_cloud_config() -> tuple[str, str, str]:
    """Get cloud URL, token, and installation ID. Raises 400 if not configured."""
    settings = get_settings()
    cloud_url = settings.get("cloudUrl")
    cloud_token = settings.get("cloudToken")
    install_id = settings.get("installationId")
    if not cloud_url or not cloud_token:
        raise HTTPException(status_code=400, detail="Not connected to cloud")
    if not install_id:
        raise HTTPException(status_code=400, detail="No installation ID")
    return cloud_url, cloud_token, install_id


@router.post("/push")
async def push_backup():
    """Collect local data and push to cloud."""
    cloud_url, cloud_token, install_id = _get_cloud_config()
    settings = get_settings()

    include_api_keys = settings.get("backupIncludeApiKeys", True)
    data = await asyncio.get_event_loop().run_in_executor(
        None, collect_backup_data, include_api_keys
    )

    # Encrypt if passphrase is set
    passphrase = settings.get("backupPassphrase")
    encrypted = False
    upload_data: dict | str = data
    if passphrase:
        upload_data = await asyncio.get_event_loop().run_in_executor(
            None, encrypt_data, data, passphrase
        )
        encrypted = True

    meta = get_backup_meta(data)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                f"{cloud_url}/api/backup/{install_id}",
                json={
                    "data": upload_data,
                    "encrypted": encrypted,
                    "meta": meta,
                    "version": 1,
                },
                headers={"Authorization": f"Bearer {cloud_token}"},
            )
            resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cloud backup failed: {e}")

    # Update local backup status
    data_hash = compute_data_hash(data)
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    current = get_settings()
    merged = deep_merge(current, {"lastBackupTime": now, "lastBackupHash": data_hash})
    settings_table.truncate()
    settings_table.insert(merged)

    return {"status": "ok", "lastBackupTime": now, "lastBackupHash": data_hash}


class RestoreRequest(BaseModel):
    passphrase: str | None = None


@router.post("/restore")
async def restore_backup(body: RestoreRequest | None = None):
    """Pull backup from cloud and overwrite local files."""
    cloud_url, cloud_token, install_id = _get_cloud_config()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{cloud_url}/api/backup/{install_id}",
                headers={"Authorization": f"Bearer {cloud_token}"},
            )
            resp.raise_for_status()
            backup = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="No backup found")
        raise HTTPException(status_code=502, detail=f"Cloud request failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cloud request failed: {e}")

    data = backup.get("data")
    if backup.get("encrypted"):
        passphrase = body.passphrase if body else None
        if not passphrase:
            raise HTTPException(status_code=400, detail="Backup is encrypted — passphrase required")
        try:
            data = decrypt_data(data, passphrase)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    await asyncio.get_event_loop().run_in_executor(None, apply_backup_data, data)

    return {"status": "ok"}


@router.get("/status")
async def backup_status():
    """Return current backup status."""
    settings = get_settings()
    return {
        "enabled": settings.get("backupEnabled", False),
        "includeApiKeys": settings.get("backupIncludeApiKeys", True),
        "lastBackupTime": settings.get("lastBackupTime"),
        "lastBackupHash": settings.get("lastBackupHash"),
        "hasPassphrase": bool(settings.get("backupPassphrase")),
    }


class ToggleRequest(BaseModel):
    enabled: bool


@router.post("/toggle")
async def toggle_backup(body: ToggleRequest):
    """Enable or disable auto-backup."""
    current = get_settings()
    merged = deep_merge(current, {"backupEnabled": body.enabled})
    settings_table.truncate()
    settings_table.insert(merged)
    return {"status": "ok", "enabled": body.enabled}


@router.delete("")
async def delete_backup():
    """Delete the cloud backup for this installation."""
    cloud_url, cloud_token, install_id = _get_cloud_config()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{cloud_url}/api/backup/{install_id}",
                headers={"Authorization": f"Bearer {cloud_token}"},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="No backup found")
        raise HTTPException(status_code=502, detail=f"Cloud request failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cloud request failed: {e}")

    # Clear local backup status
    current = get_settings()
    current.pop("lastBackupTime", None)
    current.pop("lastBackupHash", None)
    settings_table.truncate()
    settings_table.insert(current)

    return {"status": "ok"}
