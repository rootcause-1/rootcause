"""Watch recovery after an action: success when every alert in the incident is resolved within
verify.timeout_seconds (150 s).

(Alerts only resolve after 3 healthy ticks, so "all resolved" already means "healthy for 3 ticks".)
Success -> Action.status='verified', resolve_incident (status, ttr_ms, RESOLVED_BY), memory, report.
Timeout -> Action.status='failed' and the incident goes back to 'needs_action' so the next proposal is made.
Queries: get_incident (facts.py), set_action_props, resolve_incident, set_incident_props.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from rootcause import facts
from rootcause.engine import memory
from rootcause.graph.client import GraphDB
from rootcause.util import now_ms

log = logging.getLogger(__name__)


def recovered(alerts: list[dict[str, Any]]) -> bool:
    return bool(alerts) and all(a.get("status") == "resolved" for a in alerts)


async def check(db: GraphDB, incident_id: str) -> dict[str, Any]:
    inc = await facts.incident(db, incident_id)
    if inc is None:
        return {"error": f"no incident {incident_id}"}
    firing = [a for a in inc["alerts"] if a["status"] == "firing"]
    return {"incident": incident_id, "status": inc["status"], "recovered": recovered(inc["alerts"]) or
            inc["status"] == "resolved", "firing": [f"{a['target']}:{a['kind']}" for a in firing],
            "evidence": [incident_id, *{a["target"] for a in firing}]}


async def finalize(db: GraphDB, incident_id: str, action_id: str | None, strong: float) -> None:
    if action_id:
        await db.run("set_action_props", id=action_id, props={"status": "verified", "verified_ts": now_ms()})
    await db.run("resolve_incident", id=incident_id, now=now_ms(), resolution="fixed" if action_id else "recovered",
                 action=action_id)
    await db.run("set_incident_props", id=incident_id, props={"agent_state": "done"})
    await memory.remember(db, incident_id, strong)


async def watch(db: GraphDB, incident_id: str, action_id: str, timeout_s: float, tick_s: float, strong: float,
                on_done: Callable[[str, bool], Awaitable[None]] | None = None) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout_s
    ok = False
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(tick_s)
        st = await check(db, incident_id)
        if st.get("recovered"):
            ok = True
            break
    if ok:
        await finalize(db, incident_id, action_id, strong)
        log.info("incident %s verified recovered after %s", incident_id, action_id)
    else:
        await db.run("set_action_props", id=action_id, props={"status": "failed", "verified_ts": now_ms()})
        await db.run("set_incident_props", id=incident_id, props={"agent_state": "needs_action"})
        log.info("action %s did not recover %s within %ss", action_id, incident_id, timeout_s)
    if on_done:
        await on_done(incident_id, ok)
    return ok
