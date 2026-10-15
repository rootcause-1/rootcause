"""Docker stats (CPU %, memory MB, memory slope) for every demo container, plus docker events (restarts).

Live source only; the numbers are written by the pipeline with `upsert_containers` and events become
`(:Change {kind:'restart'|'die'})` via `create_container_change`. Pure helpers (cpu_percent, slope) are unit-tested.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

log = logging.getLogger(__name__)


def cpu_percent(stats: dict[str, Any]) -> float:
    cpu = stats.get("cpu_stats", {})
    pre = stats.get("precpu_stats", {})
    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - pre.get("cpu_usage", {}).get("total_usage", 0)
    sys_delta = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
    ncpu = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
    if cpu_delta <= 0 or sys_delta <= 0:
        return 0.0
    return cpu_delta / sys_delta * ncpu * 100.0


def mem_mb(stats: dict[str, Any]) -> float:
    m = stats.get("memory_stats", {})
    usage = m.get("usage", 0)
    cache = (m.get("stats") or {}).get("inactive_file", 0)
    return max(0, usage - cache) / (1024 * 1024)


def slope_per_min(points: list[tuple[int, float]]) -> float:
    """Least-squares slope of (ts_ms, value) in value-units per minute."""
    if len(points) < 3:
        return 0.0
    xs = [t / 60_000.0 for t, _ in points]
    ys = [v for _, v in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return 0.0 if den == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den


class DockerSource:
    def __init__(self, compose_project: str, parallelism: int = 8):
        import docker  # imported lazily: replay deployments have no docker socket

        self.client = docker.from_env()
        self.project = compose_project
        self.pool = ThreadPoolExecutor(max_workers=parallelism)

    def _containers(self) -> list[Any]:
        return self.client.containers.list(filters={"label": f"com.docker.compose.project={self.project}"})

    def _one(self, c: Any) -> dict[str, Any] | None:
        try:
            st = c.stats(stream=False)
            return {"container": c.name, "service": c.labels.get("com.docker.compose.service"),
                    "cpu_pct": cpu_percent(st), "mem_mb": mem_mb(st)}
        except Exception as exc:
            log.debug("stats %s: %s", c.name, exc)
            return None

    async def sample(self) -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        containers = await loop.run_in_executor(self.pool, self._containers)
        results = await asyncio.gather(*(loop.run_in_executor(self.pool, self._one, c) for c in containers))
        return [r for r in results if r]

    def watch_events(self, on_event: Callable[[dict[str, Any]], None]) -> threading.Thread:
        """Background thread: restart/die events -> on_event({container, service, action, ts})."""
        def loop() -> None:
            while True:
                try:
                    for ev in self.client.events(decode=True, filters={
                            "type": "container", "event": ["restart", "die"],
                            "label": f"com.docker.compose.project={self.project}"}):
                        attrs = ev.get("Actor", {}).get("Attributes", {})
                        on_event({"container": attrs.get("name"), "service": attrs.get("com.docker.compose.service"),
                                  "action": ev.get("Action") or ev.get("status"),
                                  "ts": int(ev.get("timeNano", time.time_ns())) // 1_000_000})
                except Exception as exc:
                    log.warning("docker events stream ended: %s; retrying", exc)
                    time.sleep(5)

        t = threading.Thread(target=loop, name="docker-events", daemon=True)
        t.start()
        return t
