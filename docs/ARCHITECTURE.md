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
6. Passive datastores (17 Oct): a database with no change and no cpu/memory/gc alarm can't be the reason a changed
   service fails, so it doesn't lower that service's depth (`blame_targets`, `ranking.passive_targets`). The
   hypothesis records which databases it `explains`.

### M6 Actions
1. Proposals: memory-backed fixes first, then flag revert (low risk), container restart (risk from betweenness and
   statefulness), and paging the owner last.
2. Approve mints a single-use token (stored hashed on the Action, 10 min TTL); execute checks it.
3. Flag reverts are atomic file replaces; restarts go through the Docker SDK; both show up as `Change(actor=rootcause)`.
4. Verification waits up to 150 s (`verify.timeout_seconds`) for every incident alert to resolve, then resolves the incident, links memory and
   writes the report; a failure re-proposes without the failed action.
5. In replay mode actions are simulated and the player jumps to the recording's recovery segment if the fix matches.

### M7 UI (17 Oct: company map + self-running demo)
1. The page is the company map (`components/ServiceMap.tsx`, SVG): customers (Journey nodes) on the left, every service
   in the lane of the Team that OWNS it (with who is on call), shared infrastructure at the bottom; live dots per call.
2. `GET /api/graph` also returns `journeys` (graph_journeys: traffic, success vs baseline, services each one critically
   REQUIRES) and `teams` (graph_teams), so one broken box visibly ripples to its team lane and to the customers.
3. `components/Narrator.tsx` tells the incident in popups, one step per stage (healthy → alerts → one incident →
   investigating → root cause → impact → fix → fixing → recovered); each step is unlocked by real Incident/Action state
   and stays up long enough to read; the map only reveals the root cause when the narrator gets there.
4. "Start demo" restarts the recording; in replay with autoplay on, the fix popup approves low-risk fixes after a visible
   12 s countdown (a real POST /approve, labelled as a demo stand-in for a person). Live mode always waits for a human.
5. Warm paper theme on semantic tokens (serif headings, mono detail), services drawn as isometric boxes, vitals card with a failing-requests timeline, tools (break, predict, memory,
   reports) in a drawer.

### Company setup and runbook automations (17 Oct)
1. Teams, people, on-call, `OWNS`, journeys (with routes) and runbooks live in the graph, seeded from `config/seed.yaml`.
2. The **Your company** tab edits them through `/api/company` (`company.py`, `company_*` queries). The next tick uses
   the edits: who gets paged (`who_owns`), business impact (journey routes, refreshed in the span window) and fixes.
3. A runbook can register an automation URL with a declared risk. It becomes a proposed action (`runbook_automations`)
   that needs the same single-use approval token. Execute POSTs the incident to the URL (simulated in replay).
4. `GET /api/company/export` writes the setup back as seed.yaml, so a company keeps it in git.

### Connect your GitHub (17 Oct)
1. `POST /api/code/scan {url}` shallow-clones a public GitHub repo (`codebase/repo.py`; only https://github.com URLs,
   no hooks, symlinks off, size cap) and `codebase/scan.py` reads it: compose services, src/ folders, .proto files,
   CODEOWNERS and flag keys known to the graph (test files ignored, generated files last).
2. `codebase/store.py` writes Repo/CodeModule/RpcService/Commit and IMPLEMENTS, DECLARES, SERVES, READ_IN, TOUCHED
   with the `code_*` queries; the scan is cached in data/code_scan.json and written again after every graph reset.
3. `code_for_node` gives the code behind a node: the incident API adds it as `code`, the chat shows it under the
   root cause, and autopilot's `read_code` step cites `code:<module>` on the trail (MCP tool `read_code` too).
4. `code_drift` lists calls seen live that the repo never declares, and declared dependencies never called.
5. Explanation only: nothing from the code reaches the ranking, so the diagnosis can't be tuned to the answer.

### Fix it in code (17 Oct)
1. When a scanned repo locates the root's code and Claude + GitHub are configured, propose adds a `code_fix` action
   (risk low: nothing runs until a person merges). The chat offers it after recovery; it is never the incident's fix.
2. Execute runs in the background: files where the root module reads the changed flag (READ_IN) are fetched from the
   fork, Claude (prompts.FIXER) answers with find/replace edits, `apply_edits` accepts them only if each matches once.
3. `codebase/github.py` creates branch `rootcause/<incident>-<ts>`, commits the files and opens the PR on
   `RC_PR_REPO` only, with the graph's evidence in the description; `create_pull_request` records FIXES / CHANGES.
4. Guard rails: approval token as for every action, one PR per `code.pr_cooldown_minutes`, never merges, says the
   code was not run. Tested with a fake Claude and a fake GitHub (unit + graph test) and clicked through in the UI.

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

### What the real demo taught us (15 Oct, live runs)
1. **Telemetry shape**: the collector gzips OTLP; gRPC clients carry `rpc.method` (not `rpc.service`), so callees are
   named from it — that is how `checkout -> "badAddress"` still resolves to `payment`; the load generator and the
   browser are traced, so journeys start at the first shop span under them; flag evaluations arrive as
   `feature_flag.evaluation` span events and become `FeatureFlag-AFFECTS->Service` edges.
2. **Failures hide behind 4xx and busy services**: the frontend answers a failed checkout with HTTP 422 plus an
   exception on an inner span, and checkout is ~0.1 % of the frontend's traffic. A request counts as failed if its own
   handler errored, and the detector also watches the worst single route (`op_err_rate`) against its own baseline.
3. **Sparse traffic is not health**: a 60 s window with too few requests is `no_data`; it holds alert state instead of
   resolving it (2 min of silence does count as healthy). Latency needs ≥ 5 samples, Kafka lag ≥ 3 messages.
4. **Connections**: if ≥ 50 % of an edge's failing calls were never answered by any server span, the connection is
   the cause (`edge:A->B`) — no need to wait for the callee's traffic to vanish from the window.
5. **Noise vs. signal**: baselines learn fast for 3 minutes (α 0.1) and then slowly (α 0.01) so a leak is not absorbed
   as normal; an error alert needs ≥ 2 failed requests, a latency alert a p95 ≥ 100 ms that beats 2× baseline and
   baseline + 3σ, and the service-wide p95 needs ≥ 10 requests (routes need 5); memory slope over 2 min must hold 60 s;
   CONSUMER spans are inbound work; JVM time-in-GC is its own rule.
6. **Changes**: only *live* changes count as causes — not superseded by a later change to the same flag, not a return
   to the variant the flag had while baselines were learned, not made by RootCause itself. The diagnosis is frozen
   while an approved fix is being verified, and the report renders the agent's verdict snapshot.

## Deliberate deviations from CLAUDE.md (flagged for the team)
- **LLM temperature**: the spec asks for temperature 0, but `claude-sonnet-5-5` rejects non-default sampling
  parameters (HTTP 400). The agent pins `output_config.effort = "medium"` instead and enables server-side refusal
  fallbacks (`fallbacks: "default"`).
- **Journey ids** are `journey:<name>` so they never collide with service ids (`checkout` is both).
- **Edge-cause threshold**: "callee has zero server spans" is checked as "callee rps ≤ 10% of its baseline", because the
  60 s window still holds old spans for up to a minute after a callee disappears.
- **UI package manager**: npm (with a committed lockfile) instead of pnpm, which was not installed on the dev machine.
- **mcp SDK** pinned `<2` because 2.x renamed `FastMCP`.
