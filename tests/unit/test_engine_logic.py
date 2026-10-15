"""Pure engine logic: ranking math, grouping, memory, prediction rules, safety, evidence entry, action order."""

import pytest

from rootcause.actions.service import confirm_phrase, order
from rootcause.chaos import baselines
from rootcause.chaos.scorecard import render
from rootcause.engine import evidence, grouping, memory, predict, ranking, safety
from rootcause.engine.impact import impact_pct

W = {"depth": 0.30, "self": 0.25, "pagerank": 0.20, "change": 0.15, "memory": 0.10}


def test_depth_score():
    assert ranking.depth_score(0) == 1.0
    assert ranking.depth_score(2) == 0.25


def test_score_is_weighted_sum_and_disabled_signals_drop_out():
    c = ranking.Candidate("payment", "payment", depth=1, self=1, pagerank=1, change=1, memory=1)
    assert ranking.score(c, W) == pytest.approx(1.0)
    assert ranking.score(c, W, {"depth", "pagerank", "change", "memory"}) == pytest.approx(0.25)


def test_rank_puts_deep_self_erroring_changed_node_first():
    payment = ranking.Candidate("payment", "payment", depth=1.0, self=1.0, pagerank=1.0, change=1.0)
    checkout = ranking.Candidate("checkout", "checkout", depth=0.5, self=0.0, pagerank=0.4)
    frontend = ranking.Candidate("frontend", "frontend", depth=0.25, self=0.0, pagerank=0.1)
    ranked = ranking.rank([frontend, checkout, payment], W)
    assert [c.target for c in ranked] == ["payment", "checkout", "frontend"]
    assert ranked[0].rank == 1


def test_change_score_windows():
    onset = 60 * 60_000
    assert ranking.change_score([onset - 5 * 60_000], onset, 10, 30) == 1.0
    assert ranking.change_score([onset - 20 * 60_000], onset, 10, 30) == 0.5
    assert ranking.change_score([onset - 40 * 60_000], onset, 10, 30) == 0.0
    assert ranking.change_score([onset + 5 * 60_000], onset, 10, 30) == 0.0


def test_self_signal_error_vs_zscore():
    alerts = [{"target": "payment", "kind": "error_rate", "value": 0.5},
              {"target": "ad", "kind": "cpu", "value": 95, "baseline": 20, "dev": 5}]
    self_err = {"payment": 0.5, "checkout": 0.0}
    assert ranking.self_signal("payment", alerts, self_err) == 1.0
    assert ranking.self_signal("ad", alerts, self_err) == 1.0  # z = 15 -> capped
    assert ranking.self_signal("checkout", alerts, self_err) == 0.0


def test_normalise():
    assert ranking.normalise({"a": 2, "b": 1, "c": 9}, ["a", "b"]) == {"a": 1.0, "b": 0.5}


def test_match_components_keeps_ids_and_finds_new():
    incs = [{"id": "INC-0001", "members": ["checkout", "payment"]}]
    out, unmatched = grouping.match_components([["frontend", "checkout", "payment"], ["ad"]], incs)
    assert ("INC-0001", ["frontend", "checkout", "payment"]) in out
    assert (None, ["ad"]) in out
    assert unmatched == []
    out, unmatched = grouping.match_components([], incs)
    assert unmatched == ["INC-0001"]


def test_jaccard_and_memory_bonus():
    assert memory.jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    adj = memory.adjust([{"incident": "INC-1", "jaccard": 0.55, "root": "payment"},
                         {"incident": "INC-2", "jaccard": 0.6, "root": "cart"}], "payment")
    assert adj[0]["incident"] == "INC-1" and adj[0]["score"] == pytest.approx(0.65)
    assert memory.adjust([{"incident": "x", "jaccard": 0.95, "root": "p"}], "p")[0]["score"] == 1.0


def test_prediction_rules():
    assert predict.broken_journeys({"payment"}, {"checkout": {"payment", "checkout"}, "browse": {"frontend"}}) \
        == {"checkout"}
    pr = predict.precision_recall({"a", "b", "c"}, {"b", "c", "d", "e"})
    assert pr["precision"] == pytest.approx(0.6667, abs=1e-3) and pr["recall"] == 0.5


def test_safety_risk():
    scores = {"frontend": 10.0, "checkout": 5.0, "cart": 1.0, "ad": 0.0, "email": 0.0}
    assert safety.percentile_of(scores, "frontend") == 1.0
    assert safety.restart_risk(0.9, False) == "high"
    assert safety.restart_risk(0.2, True) == "high"
    assert safety.restart_risk(0.6, False) == "medium"
    assert safety.restart_risk(0.2, False) == "low"


def test_action_order_and_confirmation():
    props = [{"kind": "page", "risk": "none"}, {"kind": "restart", "risk": "high"},
             {"kind": "flag_revert", "risk": "low"}, {"kind": "restart", "risk": "low", "from_memory": "INC-1"}]
    ordered = order(props)
    assert [p["kind"] for p in ordered] == ["restart", "flag_revert", "restart", "page"]
    assert ordered[0].get("from_memory")
    assert confirm_phrase({"risk": "high", "target": "cart"}) == "RESTART cart"
    assert confirm_phrase({"risk": "low", "target": "cart"}) is None


def test_evidence_entry_prefers_edge_services():
    rows = [{"id": "checkout", "in_degree": 0, "rps": 9}, {"id": "frontend-proxy", "in_degree": 0, "rps": 1},
            {"id": "payment", "in_degree": 2, "rps": 1}]
    assert evidence.pick_entry(rows) == "frontend-proxy"


def test_impact_pct():
    assert impact_pct(0.4, 1.0) == pytest.approx(0.6)
    assert impact_pct(1.0, 0.9) == 0.0
    assert impact_pct(None, 1.0) == 0.0


def test_baseline_methods():
    alerts = [{"target": "frontend", "kind": "error_rate", "ts": 3, "err_rate": 0.2},
              {"target": "frontend", "kind": "latency", "ts": 4, "err_rate": 0.2},
              {"target": "payment", "kind": "error_rate", "ts": 2, "err_rate": 0.9}]
    assert baselines.loudest_alert(alerts)[0] == "frontend"
    assert baselines.first_alert(alerts)[0] == "payment"
    assert baselines.highest_error(alerts)[0] == "payment"
    hyps = [{"target": "checkout", "depth": 0.5, "self": 0.9, "pagerank": 0, "change": 0, "memory": 0},
            {"target": "payment", "depth": 1.0, "self": 0.2, "pagerank": 1, "change": 1, "memory": 0}]
    assert baselines.graph_off(hyps, W)[0] == "checkout"


def test_scorecard_render_counts_from_runs():
    runs = [{"flag": "paymentFailure", "truth": "payment", "class": "errors", "top1": True, "ttd_ms": 30000, "incident_id": "INC-1",
             "verdict": "payment", "results": '{"rootcause": ["payment"], "first_alert": ["frontend"]}'},
            {"flag": "adHighCpu", "truth": "ad", "class": "invisible", "top1": False, "ttd_ms": 50000, "incident_id": "INC-2",
             "verdict": "frontend", "miss_reason": "truth ranked 2",
             "results": '{"rootcause": ["frontend", "ad"], "first_alert": ["ad"]}'}]
    md = render(runs, "b1")
    assert "| rootcause | 50% | 100% | 40 s | 2 |" in md
    assert "| first_alert | 50% | 50% | - | 2 |" in md
    assert "truth ranked 2" in md


def test_any_of_truth():
    from rootcause.chaos.runner import truths
    from rootcause.chaos.scorecard import hit

    assert truths(["fraud-detection", "checkout"]) == ["fraud-detection", "checkout"]
    assert truths("payment") == ["payment"]
    assert hit(["checkout", "x"], "fraud-detection | checkout", 1) is True
    assert hit(["x", "y", "z", "checkout"], "fraud-detection | checkout", 3) is False


def test_scorecard_scores_every_method_on_the_same_runs():
    from rootcause.chaos.scorecard import render

    runs = [{"flag": "a", "truth": "x", "class": "errors", "top1": True, "incident_id": "INC-1", "ttd_ms": 1000,
             "results": '{"rootcause": ["x"], "loudest_alert": ["y"]}'},
            {"flag": "b", "truth": "z", "class": "errors", "top1": False, "incident_id": None, "ttd_ms": None,
             "verdict": None, "miss_reason": "no incident", "results": '{"rootcause": []}'}]
    md = render(runs, "b1")
    assert "| rootcause | 50% | 50% | 1 s | 2 |" in md
    assert "| loudest_alert | 0% | 0% | - | 2 |" in md
