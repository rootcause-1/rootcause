"""EWMA baselines and alert rules with hysteresis."""

import pytest

from rootcause.detect.baselines import ewma, update_baselines
from rootcause.detect.rules import evaluate, step_counters

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
    assert evaluate("Service", {"rps": 0.01, "err_rate": 1.0}, C)["error_rate"] is None
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
