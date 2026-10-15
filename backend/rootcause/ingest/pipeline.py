"""Input pipeline: the single entry point for every engine input, live or replayed.

Inputs are events `{"type", "ts", "data"}` of type otlp | prom | docker_stats | docker_event | flag_config | marker.
`feed()` tees each live event to the replay recorder, then applies it to the graph. Replay (replay/player.py)
calls the very same `feed()` with a time offset, so replayed scenarios go through identical code.

Queries used: upsert_services, upsert_calls, upsert_messaging, upsert_uses, upsert_journeys, set_node_props,
upsert_flag_affects, upsert_containers, create_flag_change, create_container_change, decay_stale.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

from rootcause.graph.client import GraphDB
from rootcause.ingest import flag_watcher
from rootcause.ingest.docker_stats import slope_per_min
from rootcause.ingest.otlp import parse_otlp_json
from rootcause.ingest.spans import IngestConfig, SpanWindow, WindowStats
from rootcause.util import new_id

log = logging.getLogger(__name__)

_expected_restarts: dict[str, int] = {}


def expect_restart(container: str, until_ms: int) -> None:
    """actions/containers.py registers its own restarts so the Change gets actor='rootcause'."""
    _expected_restarts[container] = until_ms


class Pipeline:
    def __init__(self, db: GraphDB, cfg: IngestConfig, recorder: Any = None, mem_window_ms: int = 120_000,
                 skip_service_link: set[str] | None = None):
        self.db = db
        self.cfg = cfg
        self.window = SpanWindow(cfg)
        self.recorder = recorder
        self.mem_window_ms = mem_window_ms
        self.mem_hist: dict[str, deque[tuple[int, float]]] = defaultdict(deque)
        self.lag_hist: dict[str, deque[tuple[int, float]]] = defaultdict(deque)
        self.flags: dict[str, str] | None = None
        self.skip_service_link = skip_service_link or set()
        self.spans_received = 0
        self.batches_received = 0

    async def feed(self, ev: dict[str, Any], offset_ms: int = 0) -> None:
        if self.recorder is not None and offset_ms == 0:
            self.recorder.write(ev)
        kind = ev.get("type")
        ts = int(ev.get("ts", 0)) + offset_ms
        data = ev.get("data")
        if kind == "otlp":
            spans = parse_otlp_json(data, offset_ms)
            self.window.add(spans)
            self.spans_received += len(spans)
            self.batches_received += 1
        elif kind == "prom":
            await self._prom(data, ts)
        elif kind == "docker_stats":
            await self._docker_stats(data, ts)
        elif kind == "docker_event":
            await self._docker_event(data, ts)
        elif kind == "flag_config":
            await self._flag_config(data, ts)
        # markers only matter to the replay player

    async def flush(self, now_ms: int) -> WindowStats:
        """Aggregate the span window and write it to the graph (one round trip per query)."""
        st = self.window.aggregate(now_ms)
        db = self.db
        if st.services:
            await db.run("upsert_services", rows=st.services, now=now_ms)
        if st.calls:
            await db.run("upsert_calls", rows=st.calls, now=now_ms)
        if st.produces or st.consumes:
            await db.run("upsert_messaging", produces=st.produces, consumes=st.consumes, queues=st.queues, now=now_ms)
        if st.uses:
            await db.run("upsert_uses", rows=st.uses, stores=st.stores, now=now_ms)
        if st.journeys:
            await db.run("upsert_journeys", journeys=st.journeys, requires=st.requires, now=now_ms)
        if st.agent_props:
            await db.run("set_node_props", rows=st.agent_props)
        if st.flag_affects:
            await db.run("upsert_flag_affects", rows=st.flag_affects, now=now_ms)
        await db.run("decay_stale", cutoff=now_ms - self.cfg.window_ms)
        return st

    async def _prom(self, rows: list[dict[str, Any]], ts: int) -> None:
        for r in rows:
            if "lag" in r["props"]:
                h = self.lag_hist[r["id"]]
                h.append((ts, float(r["props"]["lag"])))
                while h and h[0][0] < ts - 30_000:
                    h.popleft()
                r["props"]["lag_slope"] = slope_per_min(list(h))
        if rows:
            await self.db.run("set_node_props", rows=rows)

    async def _docker_stats(self, samples: list[dict[str, Any]], ts: int) -> None:
        rows = []
        for s in samples:
            h = self.mem_hist[s["container"]]
            h.append((ts, float(s["mem_mb"])))
            while h and h[0][0] < ts - self.mem_window_ms:
                h.popleft()
            service = s.get("service")
            if service in self.skip_service_link:
                service = None
            rows.append({"container": s["container"], "service": service, "cpu_pct": float(s["cpu_pct"]),
                         "mem_mb": float(s["mem_mb"]), "mem_slope": slope_per_min(list(h))})
        if rows:
            await self.db.run("upsert_containers", rows=rows, now=ts)

    async def _docker_event(self, ev: dict[str, Any], ts: int) -> None:
        container = ev.get("container")
        if not container:
            return
        actor = "rootcause" if _expected_restarts.get(container, 0) >= ts else "unknown"
        await self.db.run("create_container_change", id=new_id("CHG"), container=container,
                          kind=str(ev.get("action", "restart")), ts=ts, actor=actor, detail=ev.get("service") or "")

    async def _flag_config(self, config: dict[str, Any], ts: int) -> None:
        new = flag_watcher.default_variants(config)
        for flag, old, to in flag_watcher.diff_flags(self.flags, new):
            await self.db.run("create_flag_change", id=new_id("CHG"), flag=flag, from_variant=old, to=to, ts=ts,
                              actor=flag_watcher.actor_for(flag, to))
            log.info("flag change %s: %s -> %s", flag, old, to)
        self.flags = new
