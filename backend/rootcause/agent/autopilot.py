"""Autopilot: the same investigation as the LLM agent, as a fixed sequence of tool calls (no LLM).

get_incident -> rank_root_causes -> evidence path -> what_changed(root) -> measure_impact ->
find_similar_incidents -> who_owns(root) -> get_runbook(root) -> propose_action.
Produces the same verdict JSON shape as agent/loop.py and writes the same (:Step) trail. Default for chaos runs
and replay. Queries: through rootcause/tools.py.
"""

from __future__ import annotations

from typing import Any

from rootcause.agent.trail import Trail
from rootcause.tools import Tools


async def investigate(tools: Tools, trail: Trail, incident_id: str) -> dict[str, Any]:
    async def call(name: str, fn: Any, **args: Any) -> dict[str, Any]:
        result = await fn(**args)
        await trail.record(name, args, result)
        return result

    inc = await call("get_incident", tools.get_incident, incident_id=incident_id)
    if "error" in inc:
        return {"error": inc["error"]}
    ranked = await call("rank_root_causes", tools.rank_root_causes, incident_id=incident_id)
    top = (ranked.get("hypotheses") or [{}])[0]
    root = top.get("target")
    if not root:
        return {"root_cause": None, "confidence": 0.0, "evidence_path": [], "change": None, "impact": [],
                "proposed_actions": [], "narrative": "No hypothesis ranked yet."}
    root_node = root.split("->", 1)[1] if root.startswith("edge:") else root
    path = await call("incident_evidence_path", tools.incident_evidence_path, incident_id=incident_id)
    changed = await call("what_changed", tools.what_changed, node_id=root_node,
                         onset_ms=inc["incident"].get("onset_ts"))
    if root.startswith("edge:") and not changed.get("changes"):
        caller = root[5:].split("->", 1)[0]
        changed = await call("what_changed", tools.what_changed, node_id=caller,
                             onset_ms=inc["incident"].get("onset_ts"))
    imp = await call("measure_impact", tools.measure_impact, incident_id=incident_id)
    await call("find_similar_incidents", tools.find_similar_incidents, incident_id=incident_id)
    owner = await call("who_owns", tools.who_owns, node_id=root_node)
    await call("get_runbook", tools.get_runbook, node_id=root_node)
    proposed = await call("propose_action", tools.propose_action, incident_id=incident_id)

    change = (changed.get("changes") or [None])[0]
    impacted = [{"journey": j["journey"], "pct": j["pct"]} for j in imp.get("journeys") or [] if j["impacted"]]
    actions = [{"id": a["id"], "kind": a["kind"], "target": a["target"], "risk": a["risk"]}
               for a in proposed.get("actions") or []]
    change_txt = (f"{change.get('flag') or change.get('container')} changed "
                  f"{change.get('from_variant') or ''}→{change.get('to') or change['kind']}") if change else \
        "no change was found near onset"
    impact_txt = ", ".join("{} -{:.0%}".format(i["journey"], i["pct"]) for i in impacted) or "none measured"
    narrative = (f"Root cause is `{root}` (score {top['score']:.2f}); {change_txt}. "
                 f"Impact: {impact_txt}. "
                 f"Owner: {owner.get('team') or 'unknown'}; first proposal: "
                 f"{(actions[0]['kind'] + ' ' + actions[0]['target']) if actions else 'none'}.")
    return {"root_cause": root, "confidence": top.get("score", 0.0), "evidence_path": path.get("path") or [],
            "change": {"id": change.get("change"), "summary": change_txt} if change else None,
            "impact": impacted, "proposed_actions": actions, "narrative": narrative}
