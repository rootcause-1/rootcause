"""Every .cypher file against a real FalkorDB: a smoke run of each query, plus behaviour tests for the engine.

Covers the VERIFY item "label SET/REMOVE works" (test_anomalous_label_set_and_removed) and the shortestPath form
(test_evidence_path).
"""

from __future__ import annotations

import re

import pytest

from rootcause.engine.core import IncidentEngine
from rootcause.graph.registry import load_all
from rootcause.settings import get_settings
from tests.graph import fixtures
from tests.graph.fixtures import FAILING, NOW, ONSET

pytestmark = pytest.mark.graph

# a superset of parameters; each query only receives the ones it references
COMMON = {
    "teams": [], "people": [], "journeys": [], "runbooks": [], "flags": [], "produces": [], "consumes": [],
    "queues": [], "stores": [], "requires": [], "now": NOW, "cutoff": NOW - 60_000, "id": "INC-0001",
    "members": FAILING, "node_id": "payment", "onset": ONSET, "window_ms": 1_800_000, "from": "frontend-proxy",
    "to": "payment", "depth": 4, "failing": FAILING, "status": "all", "flag": "paymentFailure",
    "from_variant": "off", "ts": NOW, "actor": "unknown", "container": "payment-1", "kind": "restart",
    "detail": "", "target": "payment", "value": 0.5, "threshold": 0.05, "baseline": 0.0, "dev": 0.0,
    "signal": "payment:error_rate", "props": {"x": 1}, "quiet": 0, "hyps": [], "node": "payment", "edge": None,
    "score": 0.9, "changes": [], "impacts": [], "incident": "INC-0001", "n": 1, "tool": "t", "args": "{}",
    "summary": "s", "prev": None, "cited": ["payment"], "services": ["payment"], "source": "test",
    "targets": ["payment"], "params": "{}", "risk": "low", "side_effects": "{}", "reason": "r", "rank": 1,
    "action": None, "resolution": "test", "markdown": "# r", "path": "r.md", "similar": [], "batch": "b",
    "variant": "on", "truth": "payment", "class": "errors", "seed": 1, "verdict": "payment", "top1": True,
    "top3": True, "ttd_ms": 1000, "incident_id": "INC-0001", "results": "{}", "miss_reason": None, "run": "R1",
    "stale_before": NOW,
}
ROWS = {
    "upsert_services": [{"id": "x", "rps": 1.0, "err_rate": 0.0, "self_err_rate": 0.0, "p95_ms": 1.0,
                         "server_spans": 1}],
    "upsert_calls": [{"src": "x", "dst": "y", "protocol": "grpc", "rps": 1.0, "err_rate": 0.0, "p95_ms": 1.0,
                      "unanswered_rate": 0.0}],
    "upsert_uses": [{"svc": "x", "ds": "db:x", "system": "postgresql", "rps": 1.0, "err_rate": 0.0, "p95_ms": 1.0}],
    "upsert_containers": [{"container": "x-1", "service": "x", "cpu_pct": 1.0, "mem_mb": 10.0, "mem_slope": 0.0}],
    "set_node_props": [{"id": "payment", "props": {"note": 1}}],
    "set_call_baselines": [{"src": "checkout", "dst": "payment", "baseline_err": 0.0, "baseline_p95": 10.0}],
}
ID_OVERRIDES = {"create_flag_change": "CHG-x", "create_container_change": "CHG-y", "create_alert": "ALT-x",
                "create_incident": "INC-0002", "add_step": "INC-0001:S1", "save_prediction": "PRD-1",
                "get_prediction": "PRD-1", "set_prediction_props": "PRD-1", "create_action": "ACT-1",
                "get_action": "ACT-1", "set_action_props": "ACT-1", "create_report": "RPT-1",
                "create_chaos_run": "R1", "update_alert": "ALT-0", "resolve_alert": "ALT-0"}


def params_for(name: str, text: str) -> dict:
    wanted = set(re.findall(r"\$(\w+)", text))
    p = {k: v for k, v in COMMON.items() if k in wanted}
    if "rows" in wanted:
        p["rows"] = ROWS.get(name, [])
    if name in ID_OVERRIDES:
        p["id"] = ID_OVERRIDES[name]
    return p


@pytest.mark.parametrize("name", sorted(load_all()))
async def test_query_runs(db, name):
    await fixtures.build(db)
    await db.run("create_incident", id="INC-0001", now=NOW, onset=ONSET, members=FAILING)
    await db.run("rebuild_blames")
    text = "\n".join(load_all()[name].statements)
    await db.run(name, **params_for(name, text))


async def test_anomalous_label_set_and_removed(db):
    await fixtures.build(db)
    ids = {r["id"] for r in await db.run("anomalous_nodes")}
    assert ids == set(FAILING)
    await db.run("resolve_alert", id="ALT-3", target="payment", ts=NOW)
    ids = {r["id"] for r in await db.run("anomalous_nodes")}
    assert "payment" not in ids and "checkout" in ids


async def test_blames_and_wcc_group_one_incident(db):
    await fixtures.build(db)
    await db.run("create_alert", id="ALT-ad", kind="cpu", target="cart", value=95, threshold=85, baseline=20,
                 dev=5, ts=NOW, signal="cart:cpu")
    await db.run("rebuild_blames")
    comps = [sorted(r["members"]) for r in await db.run("group_incidents")]
    # cart is anomalous and called by checkout/frontend, so BLAMES joins it to the payment chain: one incident
    assert comps == [sorted([*FAILING, "cart"])]
    depth = {r["id"]: r["out_degree"] for r in await db.run("blame_depth", members=FAILING)}
    assert depth["payment"] == 0 and depth["frontend-proxy"] == 1


async def test_pagerank_favours_payment(db):
    await fixtures.build(db)
    await db.run("rebuild_blames")
    pr = {r["id"]: r["score"] for r in await db.run("pagerank_blame")}
    assert max(pr, key=pr.get) == "payment"


async def test_evidence_path(db):
    await fixtures.build(db)
    await db.run("rebuild_blames")
    rows = await db.run("evidence_path", **{"from": "frontend-proxy", "to": "payment"})
    assert rows[0]["path"] == ["frontend-proxy", "frontend", "checkout", "payment"]


async def test_upstream_bfs_and_betweenness(db):
    await fixtures.build(db)
    up = (await db.run("upstream_bfs", id="payment", depth=6))[0]["upstream"]
    assert {"checkout", "frontend", "frontend-proxy"} <= set(up)
    scores = {r["id"]: r["score"] for r in await db.run("service_betweenness")}
    assert scores["checkout"] >= scores["payment"]


async def test_recent_change_hits_payment_through_affects(db):
    await fixtures.build(db)
    rows = await db.run("recent_changes_for", node_id="payment", onset=ONSET, window_ms=30 * 60_000)
    assert rows and rows[0]["flag"] == "paymentFailure" and rows[0]["from_variant"] == "off"


async def test_engine_ranks_payment_first_and_links_change_and_impact(db):
    await fixtures.build(db)
    engine = IncidentEngine(db, get_settings())
    summaries = await engine.run(NOW)
    [inc] = [s for s in summaries if s.get("created")]
    assert inc["root"] == "payment"
    assert [c["change"] for c in inc["changes"]] == ["CHG-1"]
    assert any(i["journey"] == "journey:checkout" and i["impacted"] for i in inc["impact"])
    # ids stay stable on the next tick
    again = await engine.run(NOW + 5000)
    assert again[0]["id"] == inc["id"] and not again[0]["created"]


async def test_edge_cause_when_callee_goes_silent(db):
    await fixtures.build(db, alerts=False)
    # payment unreachable: checkout's calls go unanswered and payment has no server spans
    await db.run("upsert_services", rows=[{"id": "payment", "rps": 0.0, "err_rate": 0.0, "self_err_rate": 0.0,
                                           "p95_ms": None, "server_spans": 0}], now=NOW)
    await db.run("upsert_calls", rows=[{"src": "checkout", "dst": "payment", "protocol": "grpc", "rps": 2.0,
                                        "err_rate": 1.0, "p95_ms": 5.0, "unanswered_rate": 2.0}], now=NOW)
    for i, t in enumerate(["frontend-proxy", "frontend", "checkout"]):
        await db.run("create_alert", id=f"E-{i}", kind="error_rate", target=t, value=0.5, threshold=0.05,
                     baseline=0.0, dev=0.0, ts=ONSET + i, signal=f"{t}:error_rate")
    summaries = await IncidentEngine(db, get_settings()).run(NOW)
    assert summaries[0]["root"] == "edge:checkout->payment"


async def test_similar_incidents_jaccard(db):
    await fixtures.build(db)
    for inc in ("INC-0001", "INC-0002"):
        await db.run("create_incident", id=inc, now=NOW, onset=ONSET, members=FAILING)
        await db.run("update_incident_members", id=inc, members=FAILING, quiet=0, now=NOW)
    await db.run("resolve_incident", id="INC-0001", now=NOW, resolution="fixed", action=None)
    rows = await db.run("similar_incidents", id="INC-0002")
    assert rows[0]["incident"] == "INC-0001" and rows[0]["jaccard"] == pytest.approx(1.0)
