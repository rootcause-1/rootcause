"""The investigation tools, implemented once and shared by the MCP server, the LLM agent and autopilot.

Every tool returns a JSON-able dict with an `evidence` list of node ids (cited on the agent's Step trail).
Read tools query the graph directly. Write tools go through an `actions` backend: the in-process ActionService
(inside the API) or `ApiActions`, which forwards to the API over HTTP (inside the MCP server process), so every
side effect happens in one place.

Queries: through facts.py, engine/*, plus who_owns, get_runbook; `cypher_readonly` runs a user query via
GRAPH.RO_QUERY with a 2 s timeout and 200-row cap.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

import httpx

from rootcause import facts
from rootcause.engine import changes, evidence, impact, memory, predict, safety
from rootcause.graph.client import GraphDB
from rootcause.util import clean

FORBIDDEN = re.compile(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH|DROP|LOAD\s+CSV)\b|CALL\s+dbms|CALL\s+db\.idx",
                       re.IGNORECASE)


class ActionsBackend(Protocol):
    async def propose(self, incident_id: str) -> dict[str, Any]: ...
    async def execute(self, action_id: str, approval_token: str) -> dict[str, Any]: ...
    async def verify_recovery(self, incident_id: str) -> dict[str, Any]: ...
    async def write_report(self, incident_id: str) -> dict[str, Any]: ...


class ApiActions:
    """Forward write tools to the RootCause API (used by the standalone MCP server)."""

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self.base}{path}", json=body or {})
            return r.json()

    async def propose(self, incident_id: str) -> dict[str, Any]:
        return await self._post(f"/api/incidents/{incident_id}/propose")

    async def execute(self, action_id: str, approval_token: str) -> dict[str, Any]:
        return await self._post(f"/api/actions/{action_id}/execute", {"approval_token": approval_token})

    async def verify_recovery(self, incident_id: str) -> dict[str, Any]:
        return await self._post(f"/api/incidents/{incident_id}/verify")

    async def write_report(self, incident_id: str) -> dict[str, Any]:
        return await self._post(f"/api/incidents/{incident_id}/report")


class Tools:
    def __init__(self, db: GraphDB, actions: ActionsBackend, settings: Any):
        self.db = db
        self.actions = actions
        self.s = settings

    # ------------------------------------------------------------------ read
    async def list_incidents(self, status: str = "open") -> dict[str, Any]:
        incs = await facts.list_incidents(self.db, status)
        slim = [{"id": i["id"], "status": i["status"], "members": i.get("members"), "root": i.get("root_target"),
                 "confidence": i.get("confidence"), "created_ts": i.get("created_ts")} for i in incs]
        return {"incidents": slim, "evidence": [i["id"] for i in incs]}

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        inc = await facts.incident(self.db, incident_id)
        if inc is None:
            return {"error": f"no incident {incident_id}", "evidence": []}
        return {"incident": {k: inc.get(k) for k in ("id", "status", "members", "root_target", "confidence",
                                                     "created_ts", "onset_ts")},
                "alerts": inc["alerts"], "alert_count": len(inc["alerts"]),
                "evidence": [incident_id, *(inc.get("members") or [])]}

    async def rank_root_causes(self, incident_id: str) -> dict[str, Any]:
        inc = await facts.incident(self.db, incident_id)
        if inc is None:
            return {"error": f"no incident {incident_id}", "evidence": []}
        hyps = inc["hypotheses"]
        return {"hypotheses": hyps, "top": hyps[0]["target"] if hyps else None,
                "weights": self.s.c("engine", "weights"),
                "evidence": [h["target"] for h in hyps[:3] if not h["target"].startswith("edge:")]}

    async def trace_evidence_path(self, from_id: str, to_id: str) -> dict[str, Any]:
        if from_id == to_id:
            return {"path": [from_id], "evidence": [from_id]}
        rows = await self.db.run("evidence_path", **{"from": from_id, "to": to_id})
        p = rows[0]["path"] if rows and rows[0].get("path") else []
        return {"path": p, "found": bool(p), "evidence": p}

    async def incident_evidence_path(self, incident_id: str) -> dict[str, Any]:
        inc = await facts.incident(self.db, incident_id)
        if inc is None or not inc.get("root_target"):
            return {"path": [], "evidence": []}
        p = await evidence.path(self.db, inc.get("members") or [], inc["root_target"])
        return {"path": p, "evidence": [x for x in p if not x.startswith("edge:")]}

    async def what_changed(self, node_id: str, window_min: float = 30, onset_ms: int | None = None
                           ) -> dict[str, Any]:
        from rootcause.util import now_ms
        found = await changes.for_node(self.db, node_id, onset_ms or now_ms(), window_min)
        return {"node": node_id, "changes": found, "evidence": [node_id, *[c["change"] for c in found]]}

    async def measure_impact(self, incident_id: str) -> dict[str, Any]:
        inc = await facts.incident(self.db, incident_id)
        if inc is None:
            return {"error": f"no incident {incident_id}", "evidence": []}
        failing = list(inc.get("members") or [])
        root = inc.get("root_target") or ""
        if root.startswith("edge:"):
            failing.append(root.split("->", 1)[1])
        imp = await impact.journeys(self.db, failing)
        return {"journeys": imp, "evidence": [i["journey"] for i in imp if i["impacted"]]}

    async def blast_radius(self, node_id: str) -> dict[str, Any]:
        rows = await self.db.run("upstream_bfs", id=node_id, depth=6, exclude=sorted(self.s.non_candidates))
        up = rows[0]["upstream"] if rows else []
        ctx = await self.db.run("service_risk_context", id=node_id)
        journeys = ctx[0]["journeys"] if ctx else []
        return {"node": node_id, "upstream": up, "journeys": journeys, "evidence": [node_id, *up]}

    async def predict_failure(self, node_id: str) -> dict[str, Any]:
        return await predict.predict(self.db, node_id)

    async def find_similar_incidents(self, incident_id: str) -> dict[str, Any]:
        inc = await facts.incident(self.db, incident_id)
        sims = await memory.similar(self.db, incident_id, (inc or {}).get("root_target"))
        strong = float(self.s.c("engine", "strong_memory", default=0.6))
        return {"similar": sims, "strong_match": next((s for s in sims if s["score"] >= strong), None),
                "evidence": [s["incident"] for s in sims]}

    async def who_owns(self, node_id: str) -> dict[str, Any]:
        rows = await self.db.run("who_owns", node_id=node_id)
        if not rows:
            return {"node": node_id, "team": None, "evidence": [node_id]}
        r = rows[0]
        people = clean(r["people"], "id")
        return {"node": node_id, "team": r["team"], "team_name": r["team_name"], "people": people,
                "on_call": [p for p in people if p.get("on_call")], "evidence": [node_id, r["team"]]}

    async def get_runbook(self, node_id: str) -> dict[str, Any]:
        rows = await self.db.run("get_runbook", node_id=node_id)
        return {"node": node_id, "runbooks": rows, "evidence": [node_id, *[r["id"] for r in rows]]}

    async def cypher_readonly(self, query: str) -> dict[str, Any]:
        if FORBIDDEN.search(query):
            return {"error": "only read-only queries are allowed", "evidence": []}
        try:
            rows = await self.db.raw(query, read_only=True, timeout_ms=2000)
        except Exception as exc:
            return {"error": str(exc), "evidence": []}
        rows = rows[:200]
        ids = [v for r in rows for v in r.values() if isinstance(v, str)][:20]
        return {"rows": rows, "truncated": len(rows) == 200, "evidence": ids}

    async def safety_report(self, action_kind: str, target: str) -> dict[str, Any]:
        if action_kind == "flag_revert":
            return await safety.assess_flag(self.db, target)
        if action_kind == "restart":
            return await safety.assess_restart(self.db, target, list(self.s.c("safety", "stateful_datastores",
                                                                                default=[])),
                                               float(self.s.c("safety", "high_betweenness_percentile", default=0.8)))
        return safety.assess_page(target)

    # ------------------------------------------------------------------ write
    async def propose_action(self, incident_id: str) -> dict[str, Any]:
        return await self.actions.propose(incident_id)

    async def execute_action(self, action_id: str, approval_token: str) -> dict[str, Any]:
        return await self.actions.execute(action_id, approval_token)

    async def verify_recovery(self, incident_id: str) -> dict[str, Any]:
        return await self.actions.verify_recovery(incident_id)

    async def write_report(self, incident_id: str) -> dict[str, Any]:
        return await self.actions.write_report(incident_id)
