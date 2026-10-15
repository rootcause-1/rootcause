"""Fixture graph built through the real ingest queries: a small slice of the demo with paymentFailure active.

frontend-proxy -> frontend -> checkout -> payment (errors originate in payment)
checkout -> cart -> cache:valkey-cart ; checkout -PRODUCES_TO-> queue:orders -CONSUMED_BY-> accounting
A flag Change on paymentFailure (AFFECTS payment via the seed map) happens 2 min before the alerts.
"""

from __future__ import annotations

from rootcause.graph.client import GraphDB

NOW = 10_000_000
ONSET = NOW - 20_000
FAILING = ["frontend-proxy", "frontend", "checkout", "payment"]


async def build(db: GraphDB, *, alerts: bool = True) -> None:
    services = [
        {"id": s, "rps": 5.0, "err_rate": e, "self_err_rate": se, "p95_ms": 20.0, "server_spans": 300}
        for s, e, se in [("frontend-proxy", 0.3, 0.0), ("frontend", 0.3, 0.0), ("checkout", 0.5, 0.0),
                         ("payment", 0.6, 0.6), ("cart", 0.0, 0.0), ("accounting", 0.0, 0.0)]
    ]
    await db.run("upsert_services", rows=services, now=NOW)
    calls = [{"src": a, "dst": b, "protocol": p, "rps": 2.0, "err_rate": e, "p95_ms": 20.0, "unanswered_rate": 0.0}
             for a, b, p, e in [("frontend-proxy", "frontend", "http", 0.3), ("frontend", "checkout", "grpc", 0.5),
                                ("checkout", "payment", "grpc", 0.6), ("checkout", "cart", "grpc", 0.0),
                                ("frontend", "cart", "grpc", 0.0)]]
    await db.run("upsert_calls", rows=calls, now=NOW)
    await db.run("upsert_messaging", produces=[{"svc": "checkout", "queue": "queue:orders", "rate": 1.0}],
                 consumes=[{"queue": "queue:orders", "svc": "accounting", "rate": 1.0, "group": "accounting"}],
                 queues=[{"queue": "queue:orders", "produce_rate": 1.0, "consume_rate": 1.0}], now=NOW)
    await db.run("upsert_uses", rows=[{"svc": "cart", "ds": "cache:valkey-cart", "system": "redis", "rps": 3.0,
                                       "err_rate": 0.0, "p95_ms": 1.0}],
                 stores=[{"ds": "cache:valkey-cart", "rps": 3.0, "err_rate": 0.0, "p95_ms": 1.0}], now=NOW)
    await db.run("upsert_journeys", journeys=[{"id": "journey:checkout", "success_rate": 0.4, "rps": 1.0}],
                 requires=[{"journey": "journey:checkout", "svc": s, "share": 1.0, "critical": True}
                           for s in FAILING], now=NOW)
    await db.run("set_node_props", rows=[{"id": "journey:checkout", "props": {"bl_success_rate": 0.99}},
                                         {"id": "payment", "props": {"bl_rps": 5.0}}])
    await db.run("create_flag_change", id="CHG-1", flag="paymentFailure", from_variant="off", to="100%",
                 ts=ONSET - 120_000, actor="unknown")
    if alerts:
        for i, target in enumerate(FAILING):
            await db.run("create_alert", id=f"ALT-{i}", kind="error_rate", target=target, value=0.5, threshold=0.05,
                         baseline=0.0, dev=0.0, ts=ONSET + i * 1000, signal=f"{target}:error_rate")
