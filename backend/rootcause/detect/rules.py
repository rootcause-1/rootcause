"""Alert rules -> (:Alert)-[:FIRED_ON]->(node) and the dynamic :Anomalous label.

Every tick `Detector.run(now)`:
1. reads all alertable nodes with their metrics and baselines (read_detect_inputs) and firing alerts (open_alerts);
2. evaluates the rules (pure `evaluate`), keeps hysteresis counters `hit_<kind>` / `ok_<kind>` on the node:
   a rule must hold `hold_ticks` in a row to fire, and be healthy `resolve_ticks` in a row to resolve;
3. creates / refreshes / resolves alerts (create_alert, update_alert, resolve_alert) — these also set/remove
   :Anomalous and merge the `<node>:<kind>` SignalPattern;
4. updates EWMA baselines (learning for the first 180 s, then frozen while any incident is open).
Baselines and counters are written in one batch with set_node_props; CALLS edge baselines with set_call_baselines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from rootcause.detect.baselines import ewma, primary_label, update_baselines
from rootcause.graph.client import GraphDB
from rootcause.util import new_id

log = logging.getLogger(__name__)

RULE_KINDS = {
    "Service": ("error_rate", "latency", "memory", "cpu", "agent_loop", "llm_latency"),
    "Datastore": ("error_rate", "latency"),
    "Queue": ("lag",),
}


@dataclass
class Breach:
    kind: str
    value: float
    threshold: float
    baseline: float
    dev: float


def _f(props: dict[str, Any], key: str, default: float | None = None) -> float | None:
    v = props.get(key)
    return default if v is None else float(v)


NO_DATA = "no_data"  # too little traffic in the window to judge: neither a breach nor evidence of health


def evaluate(label: str, p: dict[str, Any], c: dict[str, Any]) -> dict[str, Breach | str | None]:
    """Evaluate every rule for one node. Returns {kind: Breach, None (healthy) or NO_DATA}. Pure; unit-tested."""
    out: dict[str, Breach | str | None] = {k: None for k in RULE_KINDS.get(label, ())}
    rps = _f(p, "rps", 0.0) or 0.0
    busy = rps >= c["min_rps"]
    if not busy:
        for kind in ("error_rate", "latency"):
            if kind in out:
                out[kind] = NO_DATA

    if "error_rate" in out and busy:
        # service-wide error rate, then the worst single route (op_err_rate), each against its own baseline
        for metric in ("err_rate", "op_err_rate"):
            err, bl, dev = _f(p, metric), _f(p, f"bl_{metric}", 0.0), _f(p, f"bl_{metric}_dev", 0.0)
            if err is None:
                continue
            thr = max(bl + c["error_sigma"] * dev, bl + c["error_floor"])
            if err > thr:
                out["error_rate"] = Breach("error_rate", err, thr, bl, dev)
                break

    if "latency" in out:
        lat, bl, dev = _f(p, "p95_ms"), _f(p, "bl_p95_ms"), _f(p, "bl_p95_ms_dev", 0.0)
        samples = _f(p, "server_spans")  # None for datastores (no per-window count): rule applies
        enough = samples is None or samples >= c.get("latency_min_samples", 0)
        if busy and not enough:
            out["latency"] = NO_DATA
        if lat is not None and bl and busy and enough:
            thr = max(c["latency_factor"] * bl, c["latency_min_ms"])
            if lat > thr:
                out["latency"] = Breach("latency", lat, thr, bl, dev)

    if "memory" in out:
        slope = _f(p, "mem_slope")
        if slope is not None and slope > c["mem_slope_mb_per_min"]:
            out["memory"] = Breach("memory", slope, c["mem_slope_mb_per_min"], _f(p, "bl_mem_slope", 0.0),
                                   _f(p, "bl_mem_slope_dev", 0.0))

    if "cpu" in out:
        cpu = _f(p, "cpu_pct")
        if cpu is not None and cpu > c["cpu_pct"]:
            out["cpu"] = Breach("cpu", cpu, c["cpu_pct"], _f(p, "bl_cpu_pct", 0.0), _f(p, "bl_cpu_pct_dev", 0.0))

    if "agent_loop" in out:
        tc, bl = _f(p, "tool_calls_per_run"), _f(p, "bl_tool_calls_per_run")
        if tc is not None and bl and tc > c["agent_loop_factor"] * bl:
            out["agent_loop"] = Breach("agent_loop", tc, c["agent_loop_factor"] * bl, bl,
                                       _f(p, "bl_tool_calls_per_run_dev", 0.0))

    if "llm_latency" in out:
        lat, bl = _f(p, "llm_p95_ms"), _f(p, "bl_llm_p95_ms")
        thr = max(c["llm_latency_factor"] * (bl or 0.0), c.get("llm_latency_min_ms", 0.0))
        if lat is not None and bl and lat > thr:
            out["llm_latency"] = Breach("llm_latency", lat, thr, bl,
                                        _f(p, "bl_llm_p95_ms_dev", 0.0))

    if "lag" in out:
        produce, consume = _f(p, "produce_rate", 0.0) or 0.0, _f(p, "consume_rate", 0.0) or 0.0
        lag, slope = _f(p, "lag"), _f(p, "lag_slope")
        starving = produce > 0 and consume < c["lag_consume_ratio"] * produce
        growing = lag is not None and lag >= c.get("lag_min_messages", 1) and slope is not None and slope > 0
        if starving or growing:
            value = lag if growing and lag is not None else (consume / produce if produce else 0.0)
            out["lag"] = Breach("lag", value, c["lag_consume_ratio"], _f(p, "bl_consume_rate", 0.0) or 0.0, 0.0)
    return out


def step_counters(breached: bool, hit: int, ok: int) -> tuple[int, int]:
    """Hysteresis counters: consecutive breached ticks and consecutive healthy ticks."""
    return (hit + 1, 0) if breached else (0, ok + 1)


class Detector:
    def __init__(self, db: GraphDB, cfg: dict[str, Any], non_candidates: set[str]):
        self.db = db
        self.c = cfg
        self.non_candidates = non_candidates
        self.started_ms: int | None = None

    def learning_left_ms(self, now_ms: int) -> int:
        if self.started_ms is None:
            return int(self.c["learn_seconds"] * 1000)
        return max(0, int(self.c["learn_seconds"] * 1000) - (now_ms - self.started_ms))

    async def run(self, now_ms: int, incidents_open: bool) -> dict[str, Any]:
        nodes = await self.db.run("read_detect_inputs")
        if self.started_ms is None and any((n["props"] or {}).get("rps") for n in nodes):
            # baselines live on the graph: after a restart with learned baselines, keep using them
            learned = any((n["props"] or {}).get("bl_rps") is not None for n in nodes)
            self.started_ms = now_ms - (int(self.c["learn_seconds"] * 1000) if learned else 0)
        learning = self.learning_left_ms(now_ms) > 0
        firing = {(a["target"], a["kind"]): a for a in await self.db.run("open_alerts")}

        prop_rows: list[dict[str, Any]] = []
        fired: list[dict[str, Any]] = []
        resolved: list[dict[str, Any]] = []
        for n in nodes:
            nid, props = n["id"], n["props"] or {}
            label = primary_label(n["labels"])
            updates: dict[str, Any] = {}
            anomalous = "Anomalous" in n["labels"]
            if nid not in self.non_candidates and not learning:
                for kind, result in evaluate(label, props, self.c).items():
                    alert = firing.get((nid, kind))
                    if result == NO_DATA:
                        # sparse traffic (e.g. checkout at ~2/min): hold state; only a long silence counts as health
                        nd = int(props.get(f"nd_{kind}", 0)) + 1
                        updates[f"nd_{kind}"] = nd
                        if nd < int(self.c.get("no_data_resolve_ticks", 24)):
                            continue
                        result = None
                    else:
                        updates[f"nd_{kind}"] = 0
                    breach = result if isinstance(result, Breach) else None
                    hit, ok = step_counters(breach is not None, int(props.get(f"hit_{kind}", 0)),
                                            int(props.get(f"ok_{kind}", 0)))
                    updates[f"hit_{kind}"], updates[f"ok_{kind}"] = hit, ok
                    hold = int((self.c.get("hold_ticks_by_kind") or {}).get(kind, self.c["hold_ticks"]))
                    if breach and not alert and hit >= hold:
                        aid = new_id("ALT")
                        await self.db.run("create_alert", id=aid, kind=kind, target=nid, value=breach.value,
                                          threshold=breach.threshold, baseline=breach.baseline, dev=breach.dev,
                                          ts=now_ms, signal=f"{nid}:{kind}")
                        fired.append({"id": aid, "kind": kind, "target": nid, "value": breach.value, "ts": now_ms})
                        anomalous = True
                    elif breach and alert:
                        await self.db.run("update_alert", id=alert["id"], value=breach.value, ts=now_ms)
                    elif not breach and alert and ok >= self.c["resolve_ticks"]:
                        await self.db.run("resolve_alert", id=alert["id"], target=nid, ts=now_ms)
                        resolved.append({"id": alert["id"], "kind": kind, "target": nid, "ts": now_ms})
            if learning or (not incidents_open and not anomalous):
                updates.update(update_baselines(label, props, self.c["ewma_alpha"]))
            if updates:
                prop_rows.append({"id": nid, "props": updates})
        if prop_rows:
            await self.db.run("set_node_props", rows=prop_rows)
        if learning or not incidents_open:
            await self._edge_baselines()
        return {"learning_left_ms": self.learning_left_ms(now_ms), "fired": fired, "resolved": resolved}

    async def _edge_baselines(self) -> None:
        rows = []
        for e in await self.db.run("read_call_edges"):
            if e["err_rate"] is None:
                continue
            err, _ = ewma(e["baseline_err"], 0.0, float(e["err_rate"]), self.c["ewma_alpha"])
            p95 = e["baseline_p95"]
            if e["p95_ms"] is not None:
                p95, _ = ewma(p95, 0.0, float(e["p95_ms"]), self.c["ewma_alpha"])
            rows.append({"src": e["src"], "dst": e["dst"], "baseline_err": err, "baseline_p95": p95})
        if rows:
            await self.db.run("set_call_baselines", rows=rows)
