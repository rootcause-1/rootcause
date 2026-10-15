"""Evidence path: the shortest BLAMES chain from the incident's entry point to the root cause.

Queries: blame_depth (to pick the entry: a member nothing blames, preferring the edge of the system),
evidence_path (shortestPath over BLAMES). For an edge cause `edge:A->B` the path ends at A, then B is appended.
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB

EDGE_TIERS = ("frontend-proxy", "frontend", "load-generator")


def pick_entry(depth_rows: list[dict[str, Any]]) -> str | None:
    """Entry = member with in_degree 0 (nothing blames it); prefer edge services, then most traffic."""
    roots = [r for r in depth_rows if int(r["in_degree"]) == 0] or depth_rows
    if not roots:
        return None
    return sorted(roots, key=lambda r: (r["id"] not in EDGE_TIERS, -(r.get("rps") or 0.0), r["id"]))[0]["id"]


async def path(db: GraphDB, members: list[str], root_target: str) -> list[str]:
    to, extra = root_target, []
    if root_target.startswith("edge:"):
        caller, callee = root_target[5:].split("->", 1)
        to, extra = caller, [callee]
    depth_rows = await db.run("blame_depth", members=members)
    entry = pick_entry(depth_rows)
    if not entry or entry == to:
        return [to, *extra]
    rows = await db.run("evidence_path", **{"from": entry, "to": to})
    found = rows[0]["path"] if rows and rows[0].get("path") else [entry, to]
    return [*found, *extra]
