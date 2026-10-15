"""EWMA baselines and alert rules with hysteresis."""

import pytest

from rootcause.detect.baselines import ewma, update_baselines
from rootcause.detect.rules import NO_DATA, evaluate, step_counters

C = {"min_rps": 0.05, "error_sigma": 3.0, "error_floor": 0.05, "latency_factor": 2.0, "latency_min_ms": 50,
     "lag_consume_ratio": 0.2, "mem_slope_mb_per_min": 5, "cpu_pct": 85, "agent_loop_factor": 3.0,
     "llm_latency_factor": 2.0}


def test_ewma_initialises_then_smooths():
    m, d = ewma(None, None, 10.0, 0.1)
    assert (m, d) == (10.0, 0.0)
    m, d = ewma(m, d, 20.0, 0.1)
    assert m == pytest.approx(11.0) and d == pytest.approx(1.0)


def test_update_baselines_only_tracked_and_present():
    out = update_baselines("Service", {"err_rate": 0.1, "p95_ms": None, "unrelated": 5}, 0.1)
    assert set(out) == {"bl_err_rate", "bl_err_rate_dev"}


def test_error_rule_floor_catches_10_percent():
    r = evaluate("Service", {"rps": 2, "err_rate": 0.10, "bl_err_rate": 0.0, "bl_err_rate_dev": 0.0}, C)
    assert r["error_rate"] is not None and r["error_rate"].threshold == pytest.approx(0.05)


def test_error_rule_uses_sigma_when_noisy():
    p = {"rps": 2, "err_rate": 0.12, "bl_err_rate": 0.02, "bl_err_rate_dev": 0.04}  # thr = 0.02 + 0.12 = 0.14
    assert evaluate("Service", p, C)["error_rate"] is None


def test_error_rule_ignores_idle_nodes_and_noise():
    assert evaluate("Service", {"rps": 0.01, "err_rate": 1.0}, C)["error_rate"] == NO_DATA  # too quiet to judge
    assert evaluate("Service", {"rps": 5, "err_rate": 0.04, "bl_err_rate": 0.0}, C)["error_rate"] is None


def test_latency_rule_needs_double_and_50ms():
    assert evaluate("Service", {"rps": 1, "p95_ms": 30, "bl_p95_ms": 10}, C)["latency"] is None  # under 50 ms
    assert evaluate("Service", {"rps": 1, "p95_ms": 90, "bl_p95_ms": 50}, C)["latency"] is None  # under 2x
    assert evaluate("Service", {"rps": 1, "p95_ms": 120, "bl_p95_ms": 50}, C)["latency"] is not None


def test_memory_cpu_agent_rules():
    r = evaluate("Service", {"mem_slope": 8, "cpu_pct": 95, "tool_calls_per_run": 10, "bl_tool_calls_per_run": 2,
                             "llm_p95_ms": 500, "bl_llm_p95_ms": 400}, C)
    assert r["memory"] and r["cpu"] and r["agent_loop"]
    assert r["llm_latency"] is None


def test_lag_rule_starving_or_growing():
    assert evaluate("Queue", {"produce_rate": 5, "consume_rate": 0.5}, C)["lag"] is not None
    assert evaluate("Queue", {"produce_rate": 5, "consume_rate": 5, "lag": 100, "lag_slope": 30}, C)["lag"]
    assert evaluate("Queue", {"produce_rate": 5, "consume_rate": 5, "lag": 0, "lag_slope": 0}, C)["lag"] is None


def test_datastore_has_no_cpu_rule():
    assert set(evaluate("Datastore", {}, C)) == {"error_rate", "latency"}


def test_hysteresis_counters():
    hit, ok = 0, 0
    hit, ok = step_counters(True, hit, ok)
    hit, ok = step_counters(True, hit, ok)
    assert (hit, ok) == (2, 0)  # fires at hold_ticks=2
    for _ in range(3):
        hit, ok = step_counters(False, hit, ok)
    assert (hit, ok) == (0, 3)  # resolves at resolve_ticks=3


def test_route_error_rate_fires_when_service_rate_is_diluted():
    # busy frontend: 0.2% service-wide errors, but /api/checkout fails 100%
    p = {"rps": 15.0, "err_rate": 0.002, "bl_err_rate": 0.0, "op_err_rate": 1.0, "bl_op_err_rate": 0.0}
    assert evaluate("Service", p, C)["error_rate"].value == 1.0


def test_llm_latency_needs_absolute_floor():
    c = {**C, "llm_latency_min_ms": 1000}
    assert evaluate("Service", {"llm_p95_ms": 44.0, "bl_llm_p95_ms": 20.0}, c)["llm_latency"] is None
    assert evaluate("Service", {"llm_p95_ms": 5100.0, "bl_llm_p95_ms": 20.0}, c)["llm_latency"] is not None


def test_latency_and_lag_need_enough_data():
    c = {**C, "latency_min_samples": 5, "lag_min_messages": 3}
    few = {"rps": 0.05, "p95_ms": 232.0, "bl_p95_ms": 69.0, "server_spans": 3}
    assert evaluate("Service", few, c)["latency"] == NO_DATA
    assert evaluate("Service", {**few, "server_spans": 12}, c)["latency"] is not None
    q = {"produce_rate": 0.02, "consume_rate": 0.04, "lag": 1.0, "lag_slope": 2.0}
    assert evaluate("Queue", q, c)["lag"] is None
    assert evaluate("Queue", {**q, "lag": 6.0}, c)["lag"] is not None


async def test_detector_reuses_graph_baselines_after_restart():
    from rootcause.detect.rules import Detector

    class FakeDB:  # unit-level stand-in for read_detect_inputs/open_alerts only; graph behaviour is in tests/graph
        async def run(self, name, **kw):
            if name == "read_detect_inputs":
                return [{"id": "payment", "labels": ["Service"], "props": {"rps": 1.0, "bl_rps": 1.0}}]
            return []

    d = Detector(FakeDB(), {**C, "learn_seconds": 180, "ewma_alpha": 0.1, "hold_ticks": 2, "resolve_ticks": 3}, set())
    out = await d.run(1_000_000, incidents_open=False)
    assert out["learning_left_ms"] == 0


async def test_quiet_window_holds_a_firing_alert():
    from rootcause.detect.rules import Detector

    calls = []

    class FakeDB:  # unit stand-in; real graph behaviour is covered in tests/graph
        def __init__(self, props):
            self.props = props

        async def run(self, name, **kw):
            calls.append(name)
            if name == "read_detect_inputs":
                return [{"id": "payment", "labels": ["Service", "Anomalous"], "props": self.props}]
            if name == "open_alerts":
                return [{"id": "ALT-1", "target": "payment", "kind": "error_rate"}]
            return []

    cfg = {**C, "learn_seconds": 0, "ewma_alpha": 0.1, "hold_ticks": 2, "resolve_ticks": 3, "no_data_resolve_ticks": 24}
    quiet = {"rps": 0.0, "bl_rps": 0.05, "err_rate": 0.0, "ok_error_rate": 5}
    out = await Detector(FakeDB(quiet), cfg, set()).run(1_000_000, incidents_open=True)
    assert out["resolved"] == [] and "resolve_alert" not in calls
    out = await Detector(FakeDB({**quiet, "nd_error_rate": 23}), cfg, set()).run(1_000_000, incidents_open=True)
    assert [a["id"] for a in out["resolved"]] == ["ALT-1"]  # 2 min of silence counts as healthy


def test_latency_threshold_respects_normal_spread():
    c = {**C, "latency_sigma": 3.0}
    spiky = {"rps": 0.2, "p95_ms": 153.0, "bl_p95_ms": 78.0, "bl_p95_ms_dev": 30.0, "server_spans": 11}
    assert evaluate("Service", spiky, c)["latency"] is None       # 153 < 78 + 3*30
    assert evaluate("Service", {**spiky, "p95_ms": 5000.0}, c)["latency"] is not None


def test_memory_slope_respects_normal_sawtooth():
    c = {**C, "mem_sigma": 3.0}
    node = {"mem_slope": 7.4, "bl_mem_slope": 0.5, "bl_mem_slope_dev": 3.0}
    assert evaluate("Service", node, c)["memory"] is None            # 7.4 < 0.5 + 3*3
    assert evaluate("Service", {**node, "mem_slope": 40.0}, c)["memory"] is not None


def test_slowest_route_latency_fires_when_service_p95_is_diluted():
    # shipping: 1 in 28 requests (international ship-order) delayed 5 s -> service p95 unchanged, route p95 5 s
    p = {"rps": 0.5, "server_spans": 28, "p95_ms": 3.0, "bl_p95_ms": 2.0, "op_p95_ms": 5004.0, "bl_op_p95_ms": 3.0}
    assert evaluate("Service", p, C)["latency"].value == 5004.0


def test_gc_pressure_rule():
    c = {**C, "gc_min_frac": 0.05}
    assert evaluate("Service", {"gc_frac": 0.003, "bl_gc_frac": 0.001}, c)["gc"] is None
    assert evaluate("Service", {"gc_frac": 0.30, "bl_gc_frac": 0.001, "bl_gc_frac_dev": 0.001}, c)["gc"].value == 0.30


def test_one_failed_request_is_not_an_incident():
    c = {**C, "error_min_count": 2}
    p = {"rps": 0.12, "server_spans": 7, "err_rate": 1 / 7, "bl_err_rate": 0.0}
    assert evaluate("Service", p, c)["error_rate"] is None
    assert evaluate("Service", {**p, "err_rate": 2 / 7}, c)["error_rate"] is not None


async def test_baselines_adapt_slowly_after_learning():
    from rootcause.detect.rules import Detector

    written = {}

    class FakeDB:  # unit stand-in; real graph behaviour is covered in tests/graph
        async def run(self, name, **kw):
            if name == "read_detect_inputs":
                return [{"id": "email", "labels": ["Service"],
                         "props": {"rps": 1.0, "bl_rps": 1.0, "mem_slope": 20.0, "bl_mem_slope": 0.0}}]
            if name == "set_node_props":
                written.update(kw["rows"][0]["props"])
            return []

    cfg = {**C, "learn_seconds": 0, "ewma_alpha": 0.1, "ewma_alpha_live": 0.01, "hold_ticks": 2, "resolve_ticks": 3}
    await Detector(FakeDB(), cfg, set()).run(1_000_000, incidents_open=False)
    assert abs(written["bl_mem_slope"] - 0.2) < 1e-9   # 1 % step towards 20, not 10 %


def test_route_p95_counts_when_service_has_few_requests():
    c = {**C, "latency_min_samples": 10, "latency_sigma": 3.0}
    checkout = {"rps": 0.15, "server_spans": 9, "p95_ms": 1390.0, "bl_p95_ms": 60.0,
                "op_p95_ms": 1390.0, "bl_op_p95_ms": 60.0, "bl_op_p95_ms_dev": 10.0}
    assert evaluate("Service", checkout, c)["latency"].value == 1390.0
