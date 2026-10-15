"""The 5 s loop and the runtime that owns every component.

Each tick: flush the span window to the graph -> detector (alerts, :Anomalous, baselines) -> incident engine
(BLAMES, WCC, ranking) -> start the agent on incidents old enough -> push SSE events.
Live mode also runs the input sources (flagd watcher, Prometheus, docker stats/events); replay mode runs the
replay player instead. Both feed the same Pipeline.

Queries used directly: open_incidents, set_incident_props, graph_nodes, graph_edges (others via the components).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from rootcause.actions.service import ActionService
from rootcause.agent import autopilot
from rootcause.agent import loop as llm_loop
from rootcause.agent.trail import Trail
from rootcause.api.sse import Broadcaster
from rootcause.detect.rules import Detector
from rootcause.engine.core import IncidentEngine
from rootcause.graph.client import GraphDB
from rootcause.ingest.pipeline import Pipeline
from rootcause.ingest.spans import IngestConfig
from rootcause.settings import Settings
from rootcause.tools import Tools
from rootcause.util import dumps, now_ms

log = logging.getLogger(__name__)


def ingest_config(s: Settings) -> IngestConfig:
    return IngestConfig(
        window_ms=int(s.rc_window_seconds * 1000),
        finalise_lag_ms=int(s.c("ingest", "finalise_lag_ticks", default=2) * s.rc_tick_seconds * 1000),
        peer_aliases=dict(s.c("ingest", "peer_aliases", default={})),
        cache_systems=tuple(s.c("ingest", "cache_systems", default=["redis", "valkey"])),
        journey_root_services=tuple(s.c("ingest", "journey_root_services", default=["frontend-proxy", "frontend"])),
        journeys=list(s.seed.get("journeys", [])),
        journey_critical_share=float(s.c("ingest", "journey_critical_share", default=0.9)),
        agent_workflow_span=s.c("demo", "agent_workflow_span", default="astronomy_shop_agent_workflow"),
        non_candidates=frozenset(s.non_candidates),
    )


class Runtime:
    def __init__(self, s: Settings, db: GraphDB, recorder: Any = None, inline_agent: bool = False):
        self.s = s
        self.db = db
        self.sse = Broadcaster()
        self.pipeline = Pipeline(db, ingest_config(s), recorder,
                                 mem_window_ms=int(s.c("docker", "mem_slope_window_s", default=120) * 1000),
                                 skip_service_link=set(s.c("docker", "skip_service_link", default=[])))
        self.detector = Detector(db, s.c("detect"), s.non_candidates)
        self.engine = IncidentEngine(db, s)
        self.player: Any = None
        narr = llm_loop.narrator(s) if s.rc_agent_mode == "llm" else None
        self.actions = ActionService(db, s, publish=self.sse.publish, on_simulated=self._on_simulated, narrator=narr)
        self.tools = Tools(db, self.actions, s)
        self.inline_agent = inline_agent
        self.agent_mode = s.rc_agent_mode
        self.tick_n = 0
        self.last_tick_ms = 0
        self.learning_left_ms = int(s.c("detect", "learn_seconds", default=180) * 1000)
        self.started: set[str] = set()
        self.tasks: list[asyncio.Task[Any]] = []
        self.last_error: str | None = None

    # ------------------------------------------------------------------ tick
    async def tick(self, now: int | None = None) -> dict[str, Any]:
        now = now or now_ms()
        st = await self.pipeline.flush(now)
        open_before = await self.db.run("open_incidents")
        det = await self.detector.run(now, incidents_open=bool(open_before))
        summaries = await self.engine.run(now)
        self.tick_n += 1
        self.last_tick_ms = now
        self.learning_left_ms = det["learning_left_ms"]

        delay_ms = int(float(self.s.c("engine", "agent_delay_seconds", default=15)) * 1000)
        for inc in await self.db.run("open_incidents"):
            ready = now - int(inc["created_ts"] or now) >= delay_ms
            # Signals keep evolving after the first verdict (e.g. a callee's traffic only "vanishes" once the 60 s
            # window rolls over), so re-run the agent if the engine's top cause changed and nothing was approved yet.
            max_re = int(self.s.c("engine", "max_reinvestigations", default=3))
            if (inc["agent_state"] in ("awaiting_approval", "done") and inc.get("verdict_root")
                    and inc.get("root_target") and inc["root_target"] != inc["verdict_root"]
                    and int(inc.get("reinvestigations") or 0) < max_re):
                log.info("incident %s: top cause changed %s -> %s, re-investigating",
                         inc["id"], inc["verdict_root"], inc["root_target"])
                await self.db.run("set_incident_props", id=inc["id"], props={
                    "agent_state": "pending", "reinvestigations": int(inc.get("reinvestigations") or 0) + 1})
                await self.db.run("clear_proposed_actions", id=inc["id"])
                inc["agent_state"] = "pending"
                self.started.discard(inc["id"])
            if ready and inc["agent_state"] == "pending" and inc["id"] not in self.started:
                self.started.add(inc["id"])
                if self.inline_agent:
                    await self.investigate(inc["id"])
                else:
                    self.tasks.append(asyncio.ensure_future(self.investigate(inc["id"])))

        for a in det["fired"]:
            await self.sse.publish("alert", {**a, "status": "firing"})
        for a in det["resolved"]:
            await self.sse.publish("alert", {**a, "status": "resolved"})
        for inc in summaries:
            await self.sse.publish("incident", inc)
        await self.sse.publish("graph_delta", await self.graph_snapshot())
        await self.sse.publish("tick", self.status() | {"spans": st.span_count})
        return {"spans": st.span_count, "detector": det, "incidents": summaries}

    async def graph_snapshot(self) -> dict[str, Any]:
        return {"nodes": await self.db.run("graph_nodes"), "edges": await self.db.run("graph_edges")}

    def status(self) -> dict[str, Any]:
        return {"mode": self.s.rc_mode, "graph": self.db.name, "tick": self.tick_n, "tick_ts": self.last_tick_ms,
                "learning_left_ms": self.learning_left_ms, "agent_mode": self.agent_mode,
                "spans_received": self.pipeline.spans_received, "batches_received": self.pipeline.batches_received,
                "replay": self.player.status() if self.player else None, "last_error": self.last_error}

    # ------------------------------------------------------------------ agent
    async def investigate(self, incident_id: str) -> dict[str, Any]:
        await self.db.run("set_incident_props", id=incident_id, props={"agent_state": "investigating"})
        trail = Trail(self.db, incident_id, self.sse.publish)
        started = time.monotonic()
        try:
            if self.agent_mode == "llm" and self.s.anthropic_api_key:
                verdict = await llm_loop.investigate(self.s, trail, incident_id)
            else:
                verdict = await autopilot.investigate(self.tools, trail, incident_id)
        except Exception as exc:
            log.exception("agent failed on %s; falling back to autopilot", incident_id)
            self.last_error = f"agent: {exc}"
            trail = Trail(self.db, incident_id, self.sse.publish)
            trail.n = 100  # keep the failed LLM steps, number the fallback after them
            verdict = await autopilot.investigate(self.tools, trail, incident_id)
            verdict["fallback"] = "autopilot"
        verdict["verdict_ms"] = int((time.monotonic() - started) * 1000)
        verdict["verdict_ts"] = now_ms()
        await self.db.run("set_incident_props", id=incident_id, props={
            "verdict": dumps(verdict), "verdict_ts": verdict["verdict_ts"],
            "verdict_root": verdict.get("root_cause") or "",
            "agent_state": "awaiting_approval" if verdict.get("proposed_actions") else "done"})
        await self.sse.publish("incident", {"id": incident_id, "verdict": verdict})
        return verdict

    # ------------------------------------------------------------------ loops
    async def run_ticks(self) -> None:
        while True:
            t0 = time.monotonic()
            try:
                await self.tick()
                self.last_error = None if not self.last_error or self.last_error.startswith("tick") else \
                    self.last_error
            except Exception as exc:
                log.exception("tick failed")
                self.last_error = f"tick: {exc}"
            await asyncio.sleep(max(0.1, self.s.rc_tick_seconds - (time.monotonic() - t0)))

    async def start_live_sources(self) -> None:
        from rootcause.ingest.flag_watcher import FlagWatcher
        from rootcause.ingest.prom import PromSource

        s = self.s
        if s.flagd_path:
            fw = FlagWatcher(s.flagd_path, float(s.c("flagd", "poll_seconds", default=2)), self.pipeline.feed)
            self.tasks.append(asyncio.ensure_future(fw.run()))
        prom = PromSource(s.prom_url, s.c("prometheus", "queries", default={}))
        docker_src = None
        if s.c("docker", "enabled", default=True):
            try:
                from rootcause.ingest.docker_stats import DockerSource

                docker_src = DockerSource(s.c("demo", "compose_project"), int(s.c("docker", "stats_parallelism",
                                                                                     default=8)))
                loop = asyncio.get_running_loop()
                docker_src.watch_events(lambda ev: asyncio.run_coroutine_threadsafe(
                    self.pipeline.feed({"type": "docker_event", "ts": ev["ts"], "data": ev}), loop))
            except Exception as exc:
                log.warning("docker not available (%s): no container stats or restarts", exc)

        async def poll() -> None:
            while True:
                try:
                    rows = await prom.poll()
                    if rows:
                        await self.pipeline.feed({"type": "prom", "ts": now_ms(), "data": rows})
                    if docker_src:
                        samples = await docker_src.sample()
                        if samples:
                            await self.pipeline.feed({"type": "docker_stats", "ts": now_ms(), "data": samples})
                except Exception as exc:
                    log.warning("metrics poll failed: %s", exc)
                await asyncio.sleep(s.rc_tick_seconds)

        self.tasks.append(asyncio.ensure_future(poll()))

    async def _on_simulated(self, action: dict[str, Any]) -> None:
        if self.player is not None:
            self.player.notify_action(action)

    async def stop(self) -> None:
        for t in self.tasks:
            t.cancel()
