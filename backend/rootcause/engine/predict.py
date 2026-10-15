"""What-if prediction: "if X breaks, what else breaks?"

Rules:
- sync edges (grpc/http CALLS) propagate errors upstream: walk CALLED_BY with algo.bfs (query upstream_bfs).
  Kafka is not a CALLS edge, so async hops never propagate errors upstream.
- async edges propagate lag downstream: a failing consumer makes the queue it consumes lag (queues_consumed_by).
- a journey breaks when a service it REQUIRES with critical = true is predicted failing (journeys_requiring).
Saved as (:Prediction)-[:PREDICTS]->(...) (save_prediction). After the break, `score` compares against the
:Anomalous set (anomalous_nodes) for precision/recall.
"""

from __future__ import annotations

from typing import Any

from rootcause.graph.client import GraphDB
from rootcause.util import new_id, now_ms


def precision_recall(predicted: set[str], actual: set[str]) -> dict[str, float]:
    tp = len(predicted & actual)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(actual) if actual else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "true_positives": tp}


def broken_journeys(failing: set[str], requires: dict[str, set[str]]) -> set[str]:
    """requires = {journey: services it critically requires}."""
    return {j for j, svcs in requires.items() if svcs & failing}


async def predict(db: GraphDB, node_id: str, depth: int = 6, source: str = "what-if") -> dict[str, Any]:
    rows = await db.run("upstream_bfs", id=node_id, depth=depth)
    upstream = rows[0]["upstream"] if rows else []
    services = sorted({node_id, *upstream})
    queues = [r["queue"] for r in await db.run("queues_consumed_by", services=services)]
    journeys = [r["journey"] for r in await db.run("journeys_requiring", services=services)]
    pid = new_id("PRD")
    await db.run("save_prediction", id=pid, source=source, now=now_ms(), services=services, queues=queues,
                 journeys=journeys, targets=[*services, *queues, *journeys])
    return {"id": pid, "node": node_id, "services": services, "queues": queues, "journeys": journeys,
            "evidence": [*services, *queues, *journeys]}


async def score(db: GraphDB, prediction_id: str) -> dict[str, Any]:
    rows = await db.run("get_prediction", id=prediction_id)
    if not rows:
        return {"error": f"no prediction {prediction_id}"}
    p = rows[0]["prediction"]
    predicted = set(p.get("services") or []) | set(p.get("queues") or [])
    actual = {r["id"] for r in await db.run("anomalous_nodes")}
    result = precision_recall(predicted, actual)
    await db.run("set_prediction_props", id=prediction_id, props=result)
    return {**result, "predicted": sorted(predicted), "actual": sorted(actual)}
