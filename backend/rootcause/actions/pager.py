"""Page a team: append to data/pager_inbox.jsonl (shown in the UI) and POST to PAGER_WEBHOOK_URL if set.

No graph queries (the Action node records that the page happened).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from rootcause.util import now_ms

log = logging.getLogger(__name__)


def inbox_path(data_dir: str) -> Path:
    return Path(data_dir) / "pager_inbox.jsonl"


async def page(data_dir: str, webhook: str, team: str, incident_id: str, message: str) -> dict[str, Any]:
    entry = {"ts": now_ms(), "team": team, "incident": incident_id, "message": message}
    path = inbox_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    if webhook:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # "content" works for Discord, "text" for Slack
                await client.post(webhook, json={"content": f"[{team}] {incident_id}: {message}",
                                                 "text": f"[{team}] {incident_id}: {message}"})
        except Exception as exc:
            log.warning("pager webhook failed: %s", exc)
    return entry


def read_inbox(data_dir: str, limit: int = 50) -> list[dict[str, Any]]:
    path = inbox_path(data_dir)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(x) for x in reversed(lines) if x.strip()]
