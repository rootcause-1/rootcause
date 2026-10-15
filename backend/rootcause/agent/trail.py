"""Investigation trail: every tool call becomes (:Step {n, tool, args, summary, ts}) linked by NEXT, with CITED
edges to the node ids in the tool's `evidence`. Query: add_step.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from rootcause.graph.client import GraphDB
from rootcause.util import dumps, now_ms


def summarize(tool: str, result: dict[str, Any]) -> str:
    """One short, factual line per tool result (deterministic; shown in the UI trail)."""
    if "error" in result:
        return f"error: {result['error']}"
    if tool == "get_incident":
        return f"{result.get('alert_count', 0)} alerts on {', '.join(result['incident'].get('members') or [])}"
    if tool == "rank_root_causes":
        h = result.get("hypotheses") or []
        return "top: " + ", ".join(f"{x['target']} {x['score']:.2f}" for x in h[:3]) if h else "no hypotheses yet"
    if tool in ("trace_evidence_path", "incident_evidence_path"):
        return " -> ".join(result.get("path") or []) or "no path"
    if tool == "what_changed":
        ch = result.get("changes") or []
        return (f"{len(ch)} change(s): " + ", ".join(f"{c.get('flag') or c.get('container')} "
                                                     f"{c.get('from_variant') or ''}->{c.get('to') or c['kind']}"
                                                     for c in ch[:3])) if ch else "no changes near onset"
    if tool == "measure_impact":
        j = [x for x in result.get("journeys") or [] if x.get("impacted")]
        return ", ".join(f"{x['journey']} -{x['pct']:.0%}" for x in j) or "no journey impact"
    if tool == "find_similar_incidents":
        s = result.get("similar") or []
        return ", ".join(f"{x['incident']} {x['score']:.2f}" for x in s) or "no similar incidents"
    if tool == "who_owns":
        oc = result.get("on_call") or []
        return f"{result.get('team')} (on call: {', '.join(p['name'] for p in oc) or '-'})"
    if tool == "propose_action":
        a = result.get("actions") or []
        return "; ".join(f"{x['kind']} {x['target']} [{x['risk']}]" for x in a) or "nothing to propose"
    return dumps(result)[:160]


class Trail:
    def __init__(self, db: GraphDB, incident_id: str, publish: Callable[[str, Any], Awaitable[None]] | None = None):
        self.db = db
        self.incident = incident_id
        self.n = 0
        self.prev: str | None = None
        self.publish = publish

    async def record(self, tool: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        self.n += 1
        sid = f"{self.incident}:S{self.n}"
        summary = summarize(tool, result)
        cited = [c for c in result.get("evidence") or [] if isinstance(c, str)]
        await self.db.run("add_step", id=sid, incident=self.incident, n=self.n, tool=tool, args=dumps(args),
                          summary=summary, ts=now_ms(), prev=self.prev, cited=cited)
        self.prev = sid
        if self.publish:
            await self.publish("step", {"incident": self.incident, "n": self.n, "tool": tool, "summary": summary,
                                        "cited": cited})
