"""EWMA baselines per metric, persisted on the graph node itself as `bl_<metric>` and `bl_<metric>_dev`.

Pure functions; detect/rules.py reads node properties (read_detect_inputs), calls `update_baselines`, and writes
the result back with set_node_props. CALLS edges get `baseline_err` / `baseline_p95` (set_call_baselines).
"""

from __future__ import annotations

from typing import Any

# metrics we keep a baseline for, per node label
TRACKED: dict[str, tuple[str, ...]] = {
    "Service": ("rps", "err_rate", "self_err_rate", "p95_ms", "cpu_pct", "mem_slope", "tool_calls_per_run",
                "llm_p95_ms"),
    "Datastore": ("rps", "err_rate", "p95_ms"),
    "Queue": ("lag", "produce_rate", "consume_rate"),
    "Journey": ("success_rate",),
}


def ewma(mean: float | None, dev: float | None, x: float, alpha: float) -> tuple[float, float]:
    """Exponentially weighted mean and mean absolute deviation. First sample initialises the mean."""
    if mean is None:
        return float(x), 0.0
    new_mean = (1 - alpha) * mean + alpha * x
    new_dev = (1 - alpha) * (dev or 0.0) + alpha * abs(x - mean)
    return new_mean, new_dev


def update_baselines(label: str, props: dict[str, Any], alpha: float) -> dict[str, float]:
    """Return the bl_* properties after folding in the node's current metric values."""
    out: dict[str, float] = {}
    for m in TRACKED.get(label, ()):
        x = props.get(m)
        if x is None:
            continue
        mean, dev = ewma(props.get(f"bl_{m}"), props.get(f"bl_{m}_dev"), float(x), alpha)
        out[f"bl_{m}"] = mean
        out[f"bl_{m}_dev"] = dev
    return out


def primary_label(labels: list[str]) -> str:
    for label in ("Service", "Queue", "Datastore", "Journey"):
        if label in labels:
            return label
    return labels[0] if labels else ""
