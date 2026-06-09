"""Admin backup & restore — small, timestamped JSON snapshots of all
core collections stored on the local filesystem. Each backup is a
self-contained directory that can be restored with a single API call.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import require_admin
from state import (
    alerts_col, holdings_col, portfolios_col,
    transactions_col, users_col, watchlists_col,
)

logger = logging.getLogger("backup")

router = APIRouter(prefix="/api/admin", tags=["backup"])

BACKUP_DIR = Path(os.path.dirname(__file__)).parent.parent / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

COLLECTIONS: dict[str, Any] = {
    "users": users_col,
    "portfolios": portfolios_col,
    "holdings": holdings_col,
    "transactions": transactions_col,
    "watchlists": watchlists_col,
    "alerts": alerts_col,
}


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _list_backups() -> list[dict]:
    entries = []
    for d in sorted(BACKUP_DIR.iterdir()):
        if not d.is_dir() or not d.name.startswith("backup-"):
            continue
        manifest_path = d / "manifest.json"
        meta = {"name": d.name, "path": str(d)}
        if manifest_path.exists():
            try:
                meta.update(json.loads(manifest_path.read_text("utf-8")))
            except Exception:
                pass
        meta.setdefault("createdAt", datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc).isoformat())
        total_bytes = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        meta["sizeBytes"] = total_bytes
        entries.append(meta)
    return list(reversed(entries))


async def snapshot() -> str:
    """Create a timestamped snapshot of all collections. Returns the backup name."""
    stamp = _ts()
    out_dir = BACKUP_DIR / f"backup-{stamp}"
    out_dir.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "collections": {},
    }
    for name, col in COLLECTIONS.items():
        docs = await col.find({}, {"_id": 0}).to_list(50000)
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(docs, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest["collections"][name] = {"count": len(docs), "file": path.name}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Auto-backup created: %s", out_dir.name)
    return out_dir.name


async def auto_backup_loop(interval_sec: int = 1800):
    """Background task: snapshot all collections every interval_sec (default 30 min)."""
    while True:
        await asyncio.sleep(interval_sec)
        try:
            await snapshot()
        except Exception:
            logger.exception("Auto-backup failed")


@router.get("/backups")
async def list_backups(admin=Depends(require_admin)):
    return {"backups": _list_backups()}


@router.post("/backup")
async def create_backup(admin=Depends(require_admin)):
    name = await snapshot()
    return {"ok": True, "backup": name}


@router.post("/restore/{backup_name}")
async def restore_backup(backup_name: str, admin=Depends(require_admin)):
    backup_dir = BACKUP_DIR / backup_name
    if not backup_dir.is_dir():
        raise HTTPException(404, f"Backup '{backup_name}' not found")
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(400, f"Missing manifest.json in '{backup_name}'")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    restored = {}
    for name, col in COLLECTIONS.items():
        coll_info = manifest.get("collections", {}).get(name)
        if not coll_info:
            restored[name] = {"skipped": True, "reason": "not in backup manifest"}
            continue
        path = backup_dir / coll_info["file"]
        if not path.exists():
            restored[name] = {"skipped": True, "reason": "file not found"}
            continue
        docs = json.loads(path.read_text("utf-8"))
        await col.delete_many({})
        if docs:
            await col.insert_many(docs, ordered=False)
        restored[name] = {"count": len(docs)}
        logger.info("Restored %s: %d docs", name, len(docs))
    return {"ok": True, "backup": backup_name, "collections": restored}
