# Architecture

```
OpenTelemetry Demo ──OTLP/HTTP──► rootcause-api :4318 /v1/traces ─┐
 Prometheus ◄─PromQL poll── prom.py ─────────────────────────────┤
 Docker ◄─stats + events── docker_stats.py ───────────────────────┼─► Pipeline.feed() ─► FalkorDB (rc_live)
 flagd JSON ◄─poll 2 s── flag_watcher.py ─────────────────────────┘      ▲   │  (tee) ─► replay/*.jsonl.gz
                                                                          │   ▼
                    every 5 s: flush window ─► Detector ─► IncidentEngine ─► agent (autopilot | LLM over MCP)
                                                                          │
 UI (React, :8088) ◄── SSE /api/stream + REST /api/* ── FastAPI :8000 ────┘◄── MCP server :8811 (FastMCP)
```

Everything durable is in FalkorDB. The only in-process state is short-lived: the 60 s span window, 2 min metric
histories for slopes, SSE queues, and the replay player's cursor.

## How it works, by milestone

### M0–M2 Ingest
1. The demo's collector exports traces as OTLP/HTTP JSON to `rootcause-api:4318` (protobuf is accepted too).
2. Spans sit in a 60 s window keyed by trace; a span is only counted once it is 2 ticks old so late children arrive.
3. Each tick pairs CLIENT spans with their child SERVER span to get `CALLS` edges; calls nobody answered are named
   from `rpc.service`/`peer.service` aliases and counted as `unanswered`.
4. An error span with no erroring child is a *self error* of its service — that is where the failure started.
5. Everything is written with one batched `UNWIND` query per kind per tick; `decay_stale` zeroes silent services.

### M3–M4 Metrics, changes, detection
1. Docker stats give CPU/memory (+ memory slope); docker events and flagd file diffs become `(:Change)` nodes.
2. EWMA baselines (α = 0.1) live on the nodes themselves (`bl_err_rate`, …), learned for 180 s, frozen during incidents.
3. Rules (error, latency, lag, memory, cpu, agent loop, LLM latency) must hold 2 ticks to fire and be healthy 3 to resolve.
4. Firing creates `(:Alert)-[:FIRED_ON]->(node)`, sets `:Anomalous` and merges a `SignalPattern`.
5. The counters for that hysteresis are node properties too, so a restart of the API loses nothing.

### M5 Engine
1. `BLAMES` edges are rebuilt each tick between anomalous nodes: caller blames callee; a lagging queue blames its consumer.
2. `algo.WCC` over `BLAMES` turns many alerts into few incidents; ids stay stable by member overlap.
3. Each candidate gets five signals: depth (nothing left to blame), self errors, PageRank over BLAMES, a recent change
   that `AFFECTS` it, and memory of past incidents — weighted 0.30/0.25/0.20/0.15/0.10.
4. Connection faults (callee traffic vanished while callers fail) add an `edge:A->B` hypothesis; a queue whose consumer
   went silent adds that consumer (an "invisible" fault).
5. The top hypothesis gets `ROOT_CAUSE`, `CAUSED_BY` (its changes) and `IMPACTED` (journeys whose success rate dropped).

### M6 Actions
1. Proposals: memory-backed fixes first, then flag revert (low risk), container restart (risk from betweenness and
   statefulness), and paging the owner last.
2. Approve mints a single-use token (stored hashed on the Action, 10 min TTL); execute checks it.
3. Flag reverts are atomic file replaces; restarts go through the Docker SDK; both show up as `Change(actor=rootcause)`.
4. Verification waits up to 90 s for every incident alert to resolve, then resolves the incident, links memory and
   writes the report; a failure re-proposes without the failed action.
5. In replay mode actions are simulated and the player jumps to the recording's recovery segment if the fix matches.

### M8 Agent and MCP
1. `tools.py` implements every tool once; the MCP server, autopilot and the LLM agent share it.
2. The MCP server reads the graph directly and forwards write tools to the API, so side effects happen in one process.
3. Autopilot runs a fixed sequence; the LLM agent lets Claude choose tools over MCP within 12 calls / 90 s.
4. Every tool call becomes a `(:Step)` with `NEXT` and `CITED` edges — the UI highlights cited nodes on hover.
5. If the LLM path fails, autopilot takes over and the verdict says so (`fallback: autopilot`).

### M10–M11 Evaluation and replay
1. The chaos runner flips a random catalogue flag as the harness, never telling the engine, and scores the verdict.
2. Baselines (loudest/first/highest-error alert, LLM without graph, graph signals off) run on the same alert snapshot.
3. Runs are `(:ChaosRun)` nodes in `rc_eval_<batch>`; `docs/SCORECARD.md` is generated from them.
4. The recorder tees every input; the player feeds recordings through the same `Pipeline.feed()` time-shifted.
5. Golden tests replay each recording on a virtual clock and assert the top-1 matches the catalogue truth.

## Deliberate deviations from CLAUDE.md (flagged for the team)
- **LLM temperature**: the spec asks for temperature 0, but `claude-sonnet-5-5` rejects non-default sampling
  parameters (HTTP 400). The agent pins `output_config.effort = "medium"` instead and enables server-side refusal
  fallbacks (`fallbacks: "default"`).
- **Journey ids** are `journey:<name>` so they never collide with service ids (`checkout` is both).
- **Edge-cause threshold**: "callee has zero server spans" is checked as "callee rps ≤ 10% of its baseline", because the
  60 s window still holds old spans for up to a minute after a callee disappears.
- **UI package manager**: npm (with a committed lockfile) instead of pnpm, which was not installed on the dev machine.
- **mcp SDK** pinned `<2` because 2.x renamed `FastMCP`.
