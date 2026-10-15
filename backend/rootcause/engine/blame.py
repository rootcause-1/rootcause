"""Rebuild the transient BLAMES subgraph every tick (query: rebuild_blames).

BLAMES only connects :Anomalous nodes: a failing caller blames its failing callee (CALLS/USES), and a lagging
queue blames its failing consumer (async edges never blame upstream).
"""

from __future__ import annotations

from rootcause.graph.client import GraphDB


async def rebuild(db: GraphDB) -> None:
    await db.run("rebuild_blames")
