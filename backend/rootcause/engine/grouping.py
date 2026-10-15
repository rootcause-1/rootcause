"""Alert grouping: weakly connected components of BLAMES (algo.WCC, query group_incidents) -> incidents.

`match_components` (pure, unit-tested) keeps incident ids stable across ticks: each component goes to the open
incident it overlaps most; a component overlapping none becomes a new incident.
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB


async def components(db: GraphDB) -> list[list[str]]:
    # FalkorDB quirk (verified on 4.18): if a label or relationship type in algo.WCC's filter does not exist in the
    # graph yet, the filter is silently ignored and WCC runs over the WHOLE graph (teams, runbooks, flags...).
    # So: no :Anomalous nodes -> no incidents; anomalous nodes but no BLAMES edges -> each node is its own component.
    anomalous = [r["id"] for r in await db.run("anomalous_nodes")]
    if not anomalous:
        return []
    if not (await db.run("blames_count"))[0]["n"]:
        return [[a] for a in sorted(anomalous)]
    rows = await db.run("group_incidents")
    allowed = set(anomalous)
    comps = [sorted(m for m in r["members"] if m in allowed) for r in rows]
    return [c for c in comps if c]


def match_components(comps: list[list[str]], incidents: list[dict[str, Any]]
                     ) -> tuple[list[tuple[str | None, list[str]]], list[str]]:
    """Returns ([(incident_id or None for new, members)], [ids of open incidents that matched nothing])."""
    taken: set[str] = set()
    out: list[tuple[str | None, list[str]]] = []
    # biggest components choose first so a large incident keeps its id
    for comp in sorted(comps, key=len, reverse=True):
        best, best_overlap = None, 0
        for inc in incidents:
            if inc["id"] in taken:
                continue
            overlap = len(set(comp) & set(inc.get("members") or []))
            if overlap > best_overlap:
                best, best_overlap = inc["id"], overlap
        if best:
            taken.add(best)
        out.append((best, comp))
    unmatched = [inc["id"] for inc in incidents if inc["id"] not in taken]
    return out, unmatched
