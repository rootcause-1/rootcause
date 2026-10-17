"""Incident engine: runs once per tick after the detector.

1. rebuild BLAMES (engine/blame.py)
2. WCC components -> incidents with stable ids (group_incidents, open_incidents, create_incident,
   update_incident_members); incidents with no anomalous members for `recover_ticks` auto-resolve (resolve_incident)
3. for each open incident: rank candidates (blame_depth, pagerank_blame, open_alerts, edge causes, changes, memory),
   then write_hypotheses, set_root_cause, link_incident_change, link_impact.
Returns a summary per open incident for the SSE stream and the agent trigger.
"""

from __future__ import annotations

import logging
from typing import Any

from rootcause.engine import blame, changes, edge_cause, grouping, impact, memory, ranking
from rootcause.graph.client import GraphDB
from rootcause.settings import Settings

log = logging.getLogger(__name__)


class IncidentEngine:
    def __init__(self, db: GraphDB, settings: Settings):
        self.db = db
        self.s = settings
        self.weights: dict[str, float] = settings.c("engine", "weights")

    async def _next_id(self) -> str:
        rows = await self.db.run("incident_count")
        return f"INC-{int(rows[0]['n']) + 1:04d}"

    async def run(self, now_ms: int) -> list[dict[str, Any]]:
        db = self.db
        await blame.rebuild(db)
        comps = await grouping.components(db)
        open_incs = await db.run("open_incidents")
        assignments, unmatched = grouping.match_components(comps, open_incs)
        alerts = await db.run("open_alerts")

        summaries: list[dict[str, Any]] = []
        for inc_id, members in assignments:
            if inc_id is None:
                inc_id = await self._next_id()
                onset = min((a["ts"] for a in alerts if a["target"] in members), default=now_ms)
                await db.run("create_incident", id=inc_id, now=now_ms, onset=onset, members=members)
                log.info("new incident %s: %s", inc_id, members)
                created, onset_ts = True, onset
            else:
                created = False
                inc = next(i for i in open_incs if i["id"] == inc_id)
                onset_ts = inc["onset_ts"]
                if inc.get("agent_state") == "verifying":
                    # a fix is executing: keep the diagnosis as it was when the human approved it
                    await db.run("update_incident_members", id=inc_id, members=members, quiet=0, now=now_ms)
                    continue
            await db.run("update_incident_members", id=inc_id, members=members, quiet=0, now=now_ms)
            summary = await self.analyze(inc_id, members, int(onset_ts), alerts, now_ms)
            summary["created"] = created
            summaries.append(summary)

        recover = int(self.s.c("engine", "recover_ticks", default=3))
        for inc in open_incs:
            if inc["id"] not in unmatched or inc.get("agent_state") == "verifying":
                continue  # actions/verify.py resolves incidents it is watching
            quiet = int(inc.get("quiet_ticks") or 0) + 1
            if quiet >= recover:
                await db.run("resolve_incident", id=inc["id"], now=now_ms, resolution="auto-recovered", action=None)
                await memory.remember(db, inc["id"], float(self.s.c("engine", "strong_memory", default=0.6)))
                log.info("incident %s recovered without action", inc["id"])
                summaries.append({"id": inc["id"], "status": "resolved"})
            else:
                await db.run("update_incident_members", id=inc["id"], members=inc.get("members") or [], quiet=quiet,
                             now=now_ms)
        return summaries

    async def analyze(self, inc_id: str, members: list[str], onset_ms: int, alerts: list[dict[str, Any]],
                      now_ms: int, disabled: set[str] | None = None) -> dict[str, Any]:
        db = self.db
        nc = self.s.non_candidates
        depth_rows = {r["id"]: r for r in await db.run("blame_depth", members=members)}
        pr_raw = {r["id"]: float(r["score"] or 0.0) for r in await db.run("pagerank_blame")}
        pr = ranking.normalise(pr_raw, members)
        self_err = {m: float(depth_rows.get(m, {}).get("self_err_rate") or 0.0) for m in members}
        member_alerts = [a for a in alerts if a["target"] in members]

        cands: dict[str, ranking.Candidate] = {}
        for m in members:
            if m in nc:
                continue
            row = depth_rows.get(m, {})
            cands[m] = ranking.Candidate(
                target=m, node=m, depth=ranking.depth_score(int(row.get("out_degree") or 0)),
                self=ranking.self_signal(m, member_alerts, self_err), pagerank=pr.get(m, 0.0))
        for e in await edge_cause.find(db, members, now_ms):
            if e["target"] in cands and e["kind"] == "vanished_consumer":
                cands[e["target"]].self = 1.0
                continue
            cands[e["target"]] = ranking.Candidate(
                target=e["target"], node=e["node"], depth=1.0, self=1.0,
                pagerank=pr.get(e["caller"], 0.0), edge=e["edge"])

        strong, weak = self.s.c("engine", "change_strong_min"), self.s.c("engine", "change_weak_min")
        for c in cands.values():
            nodes = [c.node] if not c.edge else c.edge.split("->")
            found: list[dict[str, Any]] = []
            for n in nodes:
                found.extend(await changes.for_node(db, n, onset_ms, weak))
            c.changes = found
            c.change = ranking.change_score([int(x["ts"]) for x in found], onset_ms, strong, weak)

        # a changed service is not "further" from the cause than a passive datastore it is slowing down
        targets = {r["id"]: r["targets"] for r in await db.run("blame_targets", members=members)}
        is_store = {m: "Datastore" in (depth_rows.get(m, {}).get("labels") or []) for m in members}
        kinds: dict[str, set[str]] = {}
        for a in member_alerts:
            kinds.setdefault(a["target"], set()).add(a["kind"])
        changed = {c.target: c.change for c in cands.values()}
        for c in cands.values():
            if c.edge or c.change < 0.5 or c.target not in targets:
                continue
            passive = ranking.passive_targets(targets[c.target], is_store, changed, kinds)
            if passive:
                c.explains = passive
                c.depth = ranking.depth_score(len(targets[c.target]) - len(passive))

        sims = await memory.similar(db, inc_id)
        for c in cands.values():
            c.memory = max((s["jaccard"] for s in sims if s.get("root") == c.target), default=0.0)

        ranked = ranking.rank(list(cands.values()), self.weights, disabled)
        hyps = [{"id": f"{inc_id}:H{c.rank}", "target": c.target, "score": c.score, "rank": c.rank,
                 "explains": c.explains or None, **c.signals()} for c in ranked[:10]]
        await db.run("write_hypotheses", id=inc_id, hyps=hyps, now=now_ms)

        summary: dict[str, Any] = {"id": inc_id, "status": "open", "members": members, "hypotheses": hyps,
                                   "alert_count": len(member_alerts)}
        if ranked:
            top = ranked[0]
            await db.run("set_root_cause", id=inc_id, node=top.node, edge=top.edge, score=top.score, target=top.target)
            await db.run("link_incident_change", id=inc_id, changes=[x["change"] for x in top.changes])
            failing = sorted({*members, top.node} - nc)
            imp = await impact.journeys(db, failing)
            await db.run("link_impact", id=inc_id,
                         impacts=[{"journey": i["journey"], "pct": i["pct"]} for i in imp if i["impacted"]])
            summary.update(root=top.target, confidence=top.score, changes=top.changes, impact=imp)
        return summary
