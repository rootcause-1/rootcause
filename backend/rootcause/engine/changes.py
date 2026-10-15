"""What changed near a node: flag changes (FeatureFlag-AFFECTS->node) and container restarts (RUNS_IN).

Queries: recent_changes_for, recent_container_changes_for. Uses only the existence and timing of Change nodes;
never the chaos catalogue's flag->truth mapping.
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB


async def for_node(db: GraphDB, node_id: str, onset_ms: int, window_min: float = 30) -> list[dict[str, Any]]:
    window_ms = int(window_min * 60_000)
    flags = await db.run("recent_changes_for", node_id=node_id, onset=onset_ms, window_ms=window_ms)
    containers = await db.run("recent_container_changes_for", node_id=node_id, onset=onset_ms, window_ms=window_ms)
    out = [{"kind": "flag", **r} for r in flags] + [{**r, "kind": r.get("kind") or "restart"} for r in containers]
    # our own remediations are not causes
    return sorted((c for c in out if c.get("actor") != "rootcause"), key=lambda c: -int(c["ts"] or 0))
