"""Journey impact: which user journeys REQUIRE a failing node and how far their success rate dropped.

Query: impact_journeys. `pct` = drop relative to the journey's learned baseline success rate (0-1).
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB


def impact_pct(now: float | None, baseline: float | None) -> float:
    if now is None or not baseline:
        return 0.0
    return max(0.0, min(1.0, (baseline - now) / baseline))


async def journeys(db: GraphDB, failing: list[str], min_pct: float = 0.02) -> list[dict[str, Any]]:
    out = []
    for r in await db.run("impact_journeys", failing=failing):
        pct = impact_pct(r["now"], r["baseline"])
        out.append({"journey": r["journey"], "now": r["now"], "baseline": r["baseline"], "pct": round(pct, 4),
                    "via": r["via"], "impacted": pct >= min_pct})
    return sorted(out, key=lambda x: -x["pct"])
