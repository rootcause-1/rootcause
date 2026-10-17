"""FastAPI app: OTLP receiver (`POST /v1/traces`), the UI API (`/api/*`) and the SSE stream.

Startup: connect to FalkorDB, create indexes, seed the graph if it has no teams, build the Runtime, then start the
tick loop plus live sources (live mode) or the replay player (replay mode).
Queries used directly: graph_nodes/graph_edges (via runtime), list_reports, memory_incidents, get_prediction
(company setup queries via company.py).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from rootcause import company, facts
from rootcause.actions import pager
from rootcause.actions.flagd import read_config
from rootcause.chaos.runner import ChaosRunner, load_catalogue
from rootcause.engine import predict
from rootcause.graph.client import get_graph
from rootcause.graph.schema import ensure_indexes, load_seed
from rootcause.ingest.otlp import parse_body
from rootcause.ingest.tick import Runtime
from rootcause.replay.player import Player, list_scenarios
from rootcause.replay.recorder import Recorder
from rootcause.settings import get_settings
from rootcause.util import now_ms

log = logging.getLogger("rootcause.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class State:
    rt: Runtime
    chaos: ChaosRunner
    recorder: Recorder
    player_task: asyncio.Task[Any] | None = None


S = State()


async def _start_replay(name: str) -> dict[str, Any]:
    s = get_settings()
    path = f"{s.rc_replay_dir}/{name}.jsonl.gz"
    if S.player_task and not S.player_task.done():
        S.player_task.cancel()
    await S.rt.db.delete()  # a fresh rc_replay graph per scenario
    await ensure_indexes(S.rt.db)
    await load_seed(S.rt.db)
    S.rt.detector.started_ms = None
    S.rt.started.clear()
    S.rt.pipeline.reset()  # fresh span window + flag state for the new graph
    S.rt.player = Player(path, S.rt.pipeline.feed)
    S.player_task = asyncio.ensure_future(_replay_loop(name))
    return S.rt.player.status()


async def _replay_loop(name: str) -> None:
    """Warm up on a virtual clock, play the broken segment until a human approves the matching fix, play the
    recovery, pause, then start the scenario over on a fresh graph (the public site never goes stale)."""
    s = get_settings()
    while True:
        S.rt.paused = True
        try:
            await S.rt.player.warm(S.rt.tick, int(s.rc_tick_seconds * 1000),
                                   live_tail_ms=int(float(s.c("replay", "live_healthy_seconds", default=20)) * 1000))
        finally:
            S.rt.paused = False
        await S.rt.player.run(warmed=True, max_loops=int(s.c("replay", "max_broken_loops", default=3)))
        # after a fix: let the visitor look at the recovery and the report; unattended: start over quickly
        pause = s.c("replay", "loop_pause_seconds", default=120) if S.rt.player.fixed else 5
        await asyncio.sleep(float(pause))
        await S.rt.db.delete()
        await ensure_indexes(S.rt.db)
        await load_seed(S.rt.db)
        S.rt.detector.started_ms = None
        S.rt.started.clear()
        S.rt.pipeline.reset()
        S.rt.player = Player(f"{s.rc_replay_dir}/{name}.jsonl.gz", S.rt.pipeline.feed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    db = get_graph()
    await ensure_indexes(db)
    if not await db.raw("MATCH (t:Team) RETURN t.id AS id LIMIT 1", read_only=True):
        log.info("seeding %s: %s", db.name, await load_seed(db))
    S.recorder = Recorder(s.rc_replay_dir)
    S.rt = Runtime(s, db, recorder=S.recorder if s.rc_mode == "live" else None)
    await _refresh_journeys()  # journey routes edited in company setup live in the graph
    S.chaos = ChaosRunner(S.rt)
    S.rt.tasks.append(asyncio.ensure_future(S.rt.run_ticks()))
    if s.rc_mode == "live":
        await S.rt.start_live_sources()
    elif s.rc_replay_scenario in list_scenarios(s.rc_replay_dir):
        await _start_replay(s.rc_replay_scenario)
    elif s.rc_replay_scenario:
        log.warning("replay scenario %s not found in %s; pick one in the UI", s.rc_replay_scenario, s.rc_replay_dir)
    log.info("RootCause up: mode=%s graph=%s agent=%s", s.rc_mode, db.name, s.rc_agent_mode)
    yield
    await S.rt.stop()
    S.recorder.stop()


app = FastAPI(title="RootCause", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --------------------------------------------------------------------------- OTLP
@app.post("/v1/traces")
async def otlp_traces(request: Request) -> JSONResponse:
    body = await request.body()
    try:
        doc = parse_body(body, request.headers.get("content-type", ""), request.headers.get("content-encoding", ""))
    except Exception as exc:
        raise HTTPException(400, f"bad OTLP body: {exc}") from exc
    await S.rt.pipeline.feed({"type": "otlp", "ts": now_ms(), "data": doc})
    return JSONResponse({"partialSuccess": {}})


# --------------------------------------------------------------------------- status / graph
@app.get("/api/status")
async def status() -> dict[str, Any]:
    return S.rt.status() | {"recording": S.recorder.scenario if S.recorder.active else None,
                            "chaos": S.chaos.state}


@app.get("/api/graph")
async def graph() -> dict[str, Any]:
    return await S.rt.graph_snapshot()


@app.get("/api/stream")
async def stream() -> StreamingResponse:
    return StreamingResponse(S.rt.sse.stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------------- incidents
@app.get("/api/incidents")
async def incidents(status: str = "all") -> list[dict[str, Any]]:
    return await facts.list_incidents(S.rt.db, status)


@app.get("/api/incidents/{incident_id}")
async def incident(incident_id: str) -> dict[str, Any]:
    inc = await facts.full(S.rt.db, incident_id)
    if inc is None:
        raise HTTPException(404, "no such incident")
    root = inc.get("root_target")
    inc["evidence_path"] = (await S.rt.tools.incident_evidence_path(incident_id))["path"] if root else []
    inc["similar"] = (await S.rt.tools.find_similar_incidents(incident_id))["similar"]
    return inc


@app.post("/api/incidents/{incident_id}/investigate")
async def investigate(incident_id: str) -> dict[str, Any]:
    return await S.rt.investigate(incident_id)


@app.post("/api/incidents/{incident_id}/propose")
async def propose(incident_id: str) -> dict[str, Any]:
    return await S.rt.actions.propose(incident_id)


@app.post("/api/incidents/{incident_id}/verify")
async def verify(incident_id: str) -> dict[str, Any]:
    return await S.rt.actions.verify_recovery(incident_id)


@app.post("/api/incidents/{incident_id}/report")
async def report(incident_id: str) -> dict[str, Any]:
    return await S.rt.actions.write_report(incident_id)


# --------------------------------------------------------------------------- actions
class Approve(BaseModel):
    confirm: str | None = None
    execute: bool = True


class Execute(BaseModel):
    approval_token: str


@app.post("/api/actions/{action_id}/approve")
async def approve(action_id: str, body: Approve | None = None) -> dict[str, Any]:
    """Mints the single-use approval token. The UI approves and executes in one click (execute=true)."""
    body = body or Approve()
    out = await S.rt.actions.approve(action_id, body.confirm)
    if "error" in out:
        raise HTTPException(400, out["error"])
    if body.execute:
        result = await S.rt.actions.execute(action_id, out["approval_token"])
        return {"action": action_id, "approved": True, "execution": result}
    return out


@app.post("/api/actions/{action_id}/reject")
async def reject(action_id: str) -> dict[str, Any]:
    return await S.rt.actions.reject(action_id)


@app.post("/api/actions/{action_id}/execute")
async def execute(action_id: str, body: Execute) -> dict[str, Any]:
    return await S.rt.actions.execute(action_id, body.approval_token)


@app.get("/api/pager")
async def pager_inbox() -> list[dict[str, Any]]:
    return pager.read_inbox(get_settings().rc_data_dir)


# --------------------------------------------------------------------------- predict / memory / reports
class PredictReq(BaseModel):
    node_id: str


@app.get("/api/blast/{node_id}")
async def blast_route(node_id: str) -> dict[str, Any]:
    """Blast radius of a node: everything upstream of it (upstream_bfs) and the journeys that need it."""
    return await S.rt.tools.blast_radius(node_id)


@app.post("/api/predict")
async def predict_route(body: PredictReq) -> dict[str, Any]:
    return await predict.predict(S.rt.db, body.node_id)


@app.post("/api/predictions/{prediction_id}/score")
async def score_prediction(prediction_id: str) -> dict[str, Any]:
    return await predict.score(S.rt.db, prediction_id)


@app.get("/api/memory")
async def memory_tab() -> list[dict[str, Any]]:
    return await S.rt.db.run("memory_incidents")


@app.get("/api/reports")
async def reports() -> list[dict[str, Any]]:
    return await S.rt.db.run("list_reports")


# --------------------------------------------------------------------------- chaos
class ChaosReq(BaseModel):
    n: int = 1
    seed: int | None = None
    flag: str | None = None
    mystery: bool = False


@app.get("/api/chaos/catalogue")
async def chaos_catalogue() -> list[dict[str, Any]]:
    # the UI only needs flag names and classes; truth stays server-side until a run is scored
    return [{"flag": e["flag"], "class": e.get("class")} for e in load_catalogue()]


@app.post("/api/chaos/run")
async def chaos_run(body: ChaosReq) -> dict[str, Any]:
    if get_settings().rc_mode != "live":
        raise HTTPException(400, "chaos runs need live mode (the real demo)")
    if S.chaos.state.get("running"):
        raise HTTPException(409, "a chaos batch is already running")
    seed = body.seed if body.seed is not None else now_ms() % 100000
    S.rt.tasks.append(asyncio.ensure_future(S.chaos.run_batch(body.n, seed, body.flag, body.mystery)))
    return {"started": True, "n": body.n, "seed": seed}


@app.get("/api/chaos/status")
async def chaos_status() -> dict[str, Any]:
    return S.chaos.state


# --------------------------------------------------------------------------- record / replay
class RecordReq(BaseModel):
    scenario: str


class MarkerReq(BaseModel):
    name: str
    data: dict[str, Any] = {}


@app.post("/api/record/start")
async def record_start(body: RecordReq) -> dict[str, Any]:
    path = S.recorder.start(body.scenario, {"scenario": body.scenario})
    s = get_settings()
    if s.flagd_path:  # the flag state at the start, so a replay sees the flip as a change from it
        S.recorder.write({"type": "flag_config", "ts": now_ms(), "data": read_config(s.flagd_path)})
    return {"path": path}


@app.post("/api/record/marker")
async def record_marker(body: MarkerReq) -> dict[str, Any]:
    S.recorder.marker(body.name, body.data)
    return {"ok": True, "events": S.recorder.events}


@app.post("/api/record/stop")
async def record_stop() -> dict[str, Any]:
    events = S.recorder.events
    S.recorder.stop()
    return {"ok": True, "events": events}


@app.post("/api/admin/reset")
async def admin_reset(request: Request) -> dict[str, Any]:
    """Fresh graph. Replay: restart the current (or default) scenario. Live: re-seed and re-learn baselines.
    If RC_ADMIN_TOKEN is set, the request needs the header `x-admin-token`."""
    token = os.environ.get("RC_ADMIN_TOKEN")
    if token and request.headers.get("x-admin-token") != token:
        raise HTTPException(403, "admin token required")
    s = get_settings()
    if s.rc_mode == "replay":
        scenarios = list_scenarios(s.rc_replay_dir)
        current = S.rt.player.name if S.rt.player else None
        name = next((n for n in (current, s.rc_replay_scenario, *scenarios) if n and n in scenarios), None)
        if not name:
            raise HTTPException(404, "no replay scenarios")
        return {"reset": True, "replay": await _start_replay(name)}
    await S.rt.db.delete()
    await ensure_indexes(S.rt.db)
    await load_seed(S.rt.db)
    S.rt.detector.started_ms = None
    S.rt.started.clear()
    S.rt.pipeline.reset()
    if s.flagd_path:  # first observation of the flags = healthy baseline variants
        await S.rt.pipeline.feed({"type": "flag_config", "ts": now_ms(), "data": read_config(s.flagd_path)})
    return {"reset": True, "graph": S.rt.db.name}


# --------------------------------------------------------------------------- company setup
class CompanyEdit(BaseModel):
    kind: str            # team | journey | runbook
    item: dict[str, Any]


async def _refresh_journeys() -> None:
    S.rt.pipeline.cfg.journeys[:] = await company.journeys(S.rt.db)


@app.get("/api/company")
async def company_get() -> dict[str, Any]:
    """Teams, people, ownership, journeys and runbooks as the graph holds them, plus every known service."""
    return await company.get(S.rt.db, get_settings().non_candidates)


@app.put("/api/company")
async def company_save(body: CompanyEdit) -> dict[str, Any]:
    save = {"team": company.save_team, "journey": company.save_journey, "runbook": company.save_runbook}.get(body.kind)
    if save is None:
        raise HTTPException(400, f"unknown kind {body.kind}")
    try:
        saved = await save(S.rt.db, body.item)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if body.kind == "journey":
        await _refresh_journeys()
    return {"saved": saved}


@app.delete("/api/company/{node_id}")
async def company_delete(node_id: str) -> dict[str, Any]:
    await company.delete(S.rt.db, node_id)
    await _refresh_journeys()
    return {"deleted": node_id}


@app.post("/api/company/reset")
async def company_reset() -> dict[str, Any]:
    await company.reset(S.rt.db, get_settings().seed)
    await _refresh_journeys()
    return {"reset": True}


@app.get("/api/company/export")
async def company_export() -> PlainTextResponse:
    """The setup as seed.yaml (keep it in git; `make seed` loads it)."""
    data = company.to_seed(await company.get(S.rt.db, get_settings().non_candidates))
    data["flag_service_map"] = get_settings().seed.get("flag_service_map") or {}
    return PlainTextResponse(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), media_type="text/yaml")


@app.get("/api/replay/scenarios")
async def replay_scenarios() -> list[str]:
    return list_scenarios(get_settings().rc_replay_dir)


@app.post("/api/replay/start")
async def replay_start(body: RecordReq) -> dict[str, Any]:
    if get_settings().rc_mode != "replay":
        raise HTTPException(400, "replay needs RC_MODE=replay")
    if body.scenario not in list_scenarios(get_settings().rc_replay_dir):
        raise HTTPException(404, "unknown scenario")
    return await _start_replay(body.scenario)
