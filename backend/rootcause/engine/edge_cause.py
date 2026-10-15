"""Connection ("traffic vanished") causes. Queries: edge_candidates, vanished_consumers.

1. Caller A has failing/unanswered client spans to B, and B's server traffic vanished while it had baseline traffic
   -> hypothesis `edge:A->B` with self = 1.0 (the connection is broken, not A or B's code).
2. An anomalous queue whose consumer stopped emitting consumer spans -> hypothesis on that consumer, self = 1.0
   (an "invisible" fault: the dead consumer produces no alerts of its own).
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB


async def find(db: GraphDB, members: list[str], now_ms: int, stale_ms: int = 30_000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in await db.run("edge_candidates", members=members):
        out.append({"target": f"edge:{r['caller']}->{r['callee']}", "node": r["callee"], "caller": r["caller"],
                    "callee": r["callee"], "edge": f"{r['caller']}->{r['callee']}", "kind": "edge"})
    for r in await db.run("vanished_consumers", members=members, stale_before=now_ms - stale_ms):
        out.append({"target": r["consumer"], "node": r["consumer"], "caller": r["queue"], "callee": r["consumer"],
                    "edge": None, "kind": "vanished_consumer"})
    return out
