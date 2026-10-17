"""Side-effect report for each candidate action: {risk, affected_services, affected_journeys, stateful, reason}.

- flag revert on a flag that AFFECTS the root: risk low; affected = services the flag affects (flag_affects).
- container restart: affected = everything upstream (upstream_bfs) + journeys requiring it (service_risk_context);
  stateful if it USES a configured session store (e.g. cache:valkey-cart); risk high when the service is in the top
  20% by betweenness (service_betweenness, algo.betweenness) or stateful.
- page team: risk none.
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB
from rootcause.settings import get_settings

RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


def percentile_of(scores: dict[str, float], node: str) -> float:
    """Fraction of services with a betweenness score <= this node's (0-1)."""
    if node not in scores or not scores:
        return 0.0
    mine = scores[node]
    return sum(1 for v in scores.values() if v <= mine) / len(scores)


def restart_risk(betweenness_pct: float, stateful: bool, high_pct: float = 0.8) -> str:
    if stateful or betweenness_pct >= high_pct:
        return "high"
    return "medium" if betweenness_pct >= 0.5 else "low"


async def betweenness(db: GraphDB) -> dict[str, float]:
    return {r["id"]: float(r["score"] or 0.0) for r in await db.run("service_betweenness")}


async def assess_flag(db: GraphDB, flag: str) -> dict[str, Any]:
    rows = await db.run("flag_affects", flag=flag)
    services = rows[0]["services"] if rows else []
    return {"risk": "low", "affected_services": services, "affected_journeys": [], "stateful": False,
            "reason": f"returns {flag} to its previous variant; only touches {', '.join(services) or 'its services'}"}


async def assess_restart(db: GraphDB, service: str, stateful_stores: list[str], high_pct: float) -> dict[str, Any]:
    up = await db.run("upstream_bfs", id=service, depth=6, exclude=sorted(get_settings().non_candidates))
    upstream = up[0]["upstream"] if up else []
    ctx = await db.run("service_risk_context", id=service)
    datastores = ctx[0]["datastores"] if ctx else []
    journeys = ctx[0]["journeys"] if ctx else []
    stateful = any(d in stateful_stores for d in datastores)
    pct = percentile_of(await betweenness(db), service)
    risk = restart_risk(pct, stateful, high_pct)
    reason = f"{service} is busier than {pct:.0%} of services"
    if stateful:
        reason += f"; it holds session state in {', '.join(d for d in datastores if d in stateful_stores)}"
    return {"risk": risk, "affected_services": sorted({service, *upstream}), "affected_journeys": journeys,
            "stateful": stateful, "reason": reason, "betweenness_pct": round(pct, 3)}


def assess_automation(service: str, risk: str, title: str) -> dict[str, Any]:
    """Risk is what the owning team declared for its automation in company setup."""
    return {"risk": risk if risk in RISK_ORDER else "medium", "affected_services": [service], "affected_journeys": [],
            "stateful": False, "reason": f"runs the {service} team's own automation \"{title}\""}


def assess_page(team: str | None) -> dict[str, Any]:
    return {"risk": "none", "affected_services": [], "affected_journeys": [], "stateful": False,
            "reason": f"notifies {team or 'the owning team'}; changes nothing"}
