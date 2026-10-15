"""Read helpers that assemble one incident's facts from the graph (used by the API, tools, report and agent).

Queries: get_incident, get_steps, incident_actions, list_incidents.
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB
from rootcause.util import clean, loads


def _action(a: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in a.items() if not k.startswith("approval_")}
    out["params"] = loads(a.get("params"), {})
    out["side_effects"] = loads(a.get("side_effects"), {})
    return out


async def incident(db: GraphDB, incident_id: str) -> dict[str, Any] | None:
    rows = await db.run("get_incident", id=incident_id)
    if not rows:
        return None
    r = rows[0]
    inc = dict(r["incident"])
    inc["verdict"] = loads(inc.get("verdict"), None)
    inc["alerts"] = sorted(clean(r["alerts"], "id"), key=lambda a: a["ts"] or 0)
    inc["hypotheses"] = sorted(clean(r["hyps"], "target"), key=lambda h: h["rank"])
    inc["changes"] = clean(r["changes"], "id")
    inc["impact"] = sorted(clean(r["impact"], "journey"), key=lambda i: -(i["pct"] or 0))
    return inc


async def steps(db: GraphDB, incident_id: str) -> list[dict[str, Any]]:
    out = []
    for s in await db.run("get_steps", id=incident_id):
        out.append({**s, "args": loads(s.get("args"), {}), "cited": [c for c in s.get("cited") or [] if c]})
    return out


async def actions(db: GraphDB, incident_id: str) -> list[dict[str, Any]]:
    return [_action(r["action"]) for r in await db.run("incident_actions", id=incident_id)]


async def full(db: GraphDB, incident_id: str) -> dict[str, Any] | None:
    inc = await incident(db, incident_id)
    if inc is None:
        return None
    inc["steps"] = await steps(db, incident_id)
    inc["actions"] = await actions(db, incident_id)
    return inc


async def list_incidents(db: GraphDB, status: str = "open") -> list[dict[str, Any]]:
    out = []
    for r in await db.run("list_incidents", status=status):
        inc = dict(r["incident"])
        inc["verdict"] = loads(inc.get("verdict"), None)
        out.append(inc)
    return out
