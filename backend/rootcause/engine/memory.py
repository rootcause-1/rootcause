"""Incident memory: fingerprints (HAS_SIGNAL -> SignalPattern) and Jaccard similarity to resolved incidents.

Queries: similar_incidents, link_similar. `adjust` adds +0.1 when the past root equals the current top hypothesis
(capped at 1.0); >= 0.6 is a strong match whose fix is proposed first.
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def adjust(similar: list[dict[str, Any]], top_target: str | None) -> list[dict[str, Any]]:
    out = []
    for s in similar:
        score = float(s["jaccard"])
        if top_target and s.get("root") == top_target:
            score += 0.1
        out.append({**s, "score": round(min(1.0, score), 4)})
    return sorted(out, key=lambda s: -s["score"])


async def similar(db: GraphDB, incident_id: str, top_target: str | None = None) -> list[dict[str, Any]]:
    rows = await db.run("similar_incidents", id=incident_id)
    for r in rows:
        r["fixes"] = [f for f in r.get("fixes") or [] if f]
    return adjust(rows, top_target)


async def remember(db: GraphDB, incident_id: str, strong: float) -> list[dict[str, Any]]:
    """On resolve: link SIMILAR_TO edges to strongly matching past incidents."""
    sims = [s for s in await similar(db, incident_id) if s["score"] >= strong]
    if sims:
        await db.run("link_similar", id=incident_id,
                     similar=[{"incident": s["incident"], "score": s["score"]} for s in sims])
    return sims
