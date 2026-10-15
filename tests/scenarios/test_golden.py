"""Golden scenario tests: replay each recorded scenario in replay/ into a fresh rc_eval_test_* graph on a virtual
clock and assert the top-1 hypothesis equals the chaos catalogue truth. Guards against regressions when tuning
weights. Skips when there are no recordings or no FalkorDB.
"""

from __future__ import annotations

import uuid

import pytest
from falkordb.asyncio import FalkorDB

from rootcause.chaos.runner import load_catalogue
from rootcause.graph.client import GraphDB
from rootcause.graph.schema import ensure_indexes, load_seed
from rootcause.ingest.tick import Runtime
from rootcause.replay.player import list_scenarios, load, play_fast, segments
from rootcause.settings import get_settings

pytestmark = pytest.mark.scenario
S = get_settings()
SCENARIOS = list_scenarios(S.rc_replay_dir)
TRUTH = {e["flag"]: e["truth"] for e in load_catalogue()}


@pytest.mark.skipif(not SCENARIOS, reason="no recordings in replay/ yet (make record SCENARIO=...)")
@pytest.mark.parametrize("scenario", SCENARIOS)
async def test_top1_matches_truth(falkor_addr, scenario):
    path = f"{S.rc_replay_dir}/{scenario}.jsonl.gz"
    flag = segments(load(path))["meta"].get("flag") or scenario
    if flag not in TRUTH:
        pytest.skip(f"{scenario}: flag {flag} not in catalogue")
    host, port = falkor_addr
    db = GraphDB(f"rc_eval_test_{uuid.uuid4().hex[:8]}", FalkorDB(host=host, port=port))
    try:
        await ensure_indexes(db)
        await load_seed(db)
        s = S.model_copy(update={"rc_mode": "replay", "rc_agent_mode": "autopilot"})
        rt = Runtime(s, db, inline_agent=True)

        async def verdict_ready() -> bool:
            return any(i.get("agent_state") != "pending" for i in await db.run("open_incidents"))

        await play_fast(path, rt.pipeline.feed, rt.tick, int(s.rc_tick_seconds * 1000), until=verdict_ready)
        rows = await db.run("open_incidents")
        assert rows, f"{scenario}: no incident opened"
        hyps = (await db.run("get_incident", id=rows[0]["id"]))[0]["hyps"]
        top = sorted([h for h in hyps if h.get("target")], key=lambda h: h["rank"])[0]["target"]
        assert top == TRUTH[flag], f"{scenario}: top-1 {top}, truth {TRUTH[flag]}"
    finally:
        await db.delete()
