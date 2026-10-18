# Study guide: read the code, answer the judges

For Yash and Shambhvi before judging. Part 1 is a reading order (about 3,700 lines of backend that matter). Part 2 is
the questions judges are likely to ask, with answers taken from the code and `config/rootcause.yaml`.

## Part 1: reading order

| # | Read | What to understand |
|---|---|---|
| 1 | `docs/ARCHITECTURE.md`, `docs/GRAPH_MODEL.md` | the nine steps and every node and edge |
| 2 | `backend/rootcause/ingest/otlp.py`, `spans.py` | OTLP JSON → client/server pairing → `CALLS {rps, err_rate, p95}`, queues, `USES`, journeys, self-errors |
| 3 | `ingest/pipeline.py`, `tick.py` | the 5-second loop: flush the window into the graph, detect, run the engine, trigger the agent |
| 4 | `detect/baselines.py`, `rules.py` | EWMA baselines stored on the graph; each alert rule; hold and resolve ticks |
| 5 | `engine/core.py`, `ranking.py` | BLAMES → WCC incidents → five-signal ranking → `ROOT_CAUSE`, change, impact |
| 6 | `engine/edge_cause.py`, `evidence.py`, `safety.py`, `memory.py`, `predict.py` | "traffic vanished", proof path, risk, memory, what-if |
| 7 | `graph/queries/`: `rebuild_blames`, `group_incidents`, `pagerank_blame`, `evidence_path`, `upstream_bfs`, `service_betweenness`, `similar_incidents`, `recent_changes_for`, `code_drift` | the Cypher behind every claim |
| 8 | `mcp_server/server.py`, `tools.py`, `agent/loop.py`, `agent/autopilot.py` | the 16 tools, Gemini function calling, the Step trail, the verdict JSON |
| 9 | `actions/service.py`, `actions/verify.py`, `actions/report.py` | propose → approve (token) → execute → verify → report |
| 10 | `codebase/scan.py`, `codebase/fix.py`, `llm.py` | the code layer and *Fix it in code* |
| 11 | `chaos/runner.py`, `chaos/baselines.py`, `chaos/scorecard.py` | blind tests and how the scorecard is generated |
| 12 | `frontend/src/components/Narrator.tsx`, `ServiceMap.tsx` | the chat and map are driven by real graph state |

## Part 2: likely questions

**What does RootCause do, in one sentence?**
It turns live OpenTelemetry traces and metrics into a FalkorDB graph, finds the one real cause behind a storm of
alarms, proves it with a path in the graph, fixes it after a person approves, checks the fix worked, and can open the
code fix as a pull request.

**Why a graph? Would it work without FalkorDB?**
No. Grouping alarms is connected components (`algo.WCC` over BLAMES), "where does blame flow" is `algo.pageRank`, the
proof is `shortestPath`, blast radius is `algo.bfs` over `CALLED_BY`, restart risk is `algo.betweenness`, memory is
overlap of `SignalPattern` nodes. All state (baselines, alerts, incidents, steps, actions, code, PRs) lives in the
graph. 102 named `.cypher` files, no other database.

**Walk me through the graph model.**
`Service -CALLS-> Service` (with a mirrored `CALLED_BY` for upstream walks), `PRODUCES_TO`/`CONSUMED_BY` queues,
`USES` datastores, `RUNS_IN` containers, `Journey -REQUIRES-> Service`, `Team -OWNS-> Service`, `Person -MEMBER_OF->
Team`, `FeatureFlag -AFFECTS-> Service`, `Change -CHANGED-> FeatureFlag|Container`, `Alert -FIRED_ON-> node`,
`Alert -PART_OF-> Incident`, `Incident -ROOT_CAUSE/CAUSED_BY/IMPACTED/RESOLVED_BY->`, `Step -CITED-> node`, and the code
layer `CodeModule -IMPLEMENTS-> Service`, `DECLARES`, `SERVES -> RpcService`, `FeatureFlag -READ_IN-> CodeModule`.
Anomalous nodes get a dynamic `:Anomalous` label; `BLAMES` edges are rebuilt every tick between anomalous nodes only.
Separate graphs per mode: `rc_live`, `rc_replay`, `rc_eval_<batch>`.

**How do traces become edges?**
A CLIENT span in service A whose child SERVER span is in service B gives `A -CALLS-> B`; if the server span never
arrives, the peer attributes name B and the call counts as unanswered. Error spans whose children are all fine count
as the service's *own* errors. Root spans at the frontend give customer journeys. One batched `UNWIND` query per kind
per tick.

**How do alarms work?**
EWMA baselines on the graph (α 0.1 while learning for 180 s, then 0.01). Error rate must exceed baseline + 3σ and
baseline + 5 points, with at least 2 failed requests. Latency: p95 above 2× baseline and baseline + 3σ, at least 100 ms
and 10 samples. Plus Kafka lag, memory slope (> 5 MB/min held 60 s), CPU > 85 % for 30 s, JVM GC pressure, AI agent
loops and LLM latency. A rule must hold 2 ticks; an alert resolves after 3 healthy ticks; a window too quiet to judge
holds its state.

**How do many alarms become one incident?**
`rebuild_blames` draws `BLAMES` from each anomalous caller to each anomalous callee along `CALLS`/`USES` (weight =
error rate), and from a lagging queue to its consumer (never upstream). `algo.WCC` over `:Anomalous` + `BLAMES`
gives the components; each one is matched to an open incident by overlap so ids stay stable. Guard: FalkorDB's WCC
ignores its filters if the label doesn't exist yet, so we check first (`engine/grouping.py`).

**How is the root cause chosen?**
`score = 0.30·depth + 0.25·self + 0.20·pagerank + 0.15·change + 0.10·memory`, each normalised to 0–1.
Depth = 1 if the node blames nobody further, else 0.5^out-degree. Self = its own error share (or the anomaly z-score for
non-error alerts). PageRank over BLAMES. Change = 1.0 if a change hit it within 10 min before onset, 0.5 within 30.
Memory = similarity to a resolved past incident with this root. Two general rules: if a caller keeps calling a service
that has no traffic at all, the cause is the connection (`edge:A->B`); a database that didn't change and has no
resource alarm is a symptom of the service that uses it.

**Isn't reading the feature flag cheating?**
The engine never reads the flag config to decide. The flag watcher only records that *a change happened* and when
(`Change` nodes), and `AFFECTS` edges come from flag-evaluation events in the spans. Which flag maps to which truth
lives in the chaos catalogue and is used only to score blind tests afterwards.

**How is the answer proven?**
`evidence_path`: `shortestPath` over `BLAMES` (up to 8 hops) from the entry point to the root, drawn as the red trail.
The agent cites node ids, and every tool call is a `Step` node linked to what it cited.

**How does the agent use MCP?**
`mcp_server/server.py` exposes 16 tools (FastMCP, streamable HTTP and stdio). The Gemini agent gets their schemas
(execute, verify and report are hidden from it), chooses tools within 12 calls / 90 s, and must end with a verdict
JSON (`root_cause, confidence, evidence_path, change, impact, proposed_actions, narrative`). The autopilot runs the
same steps without an LLM and produces the same JSON.

**How do you stop the agent from doing damage?**
It can only propose. A person's approval mints a single-use token (10-minute TTL); high-risk actions need typed
confirmation. The read-only Cypher tool uses `ro_query` with a 2 s timeout, 200 rows and blocked write keywords.

**How is a fix's risk computed?**
Flag revert on a flag that `AFFECTS` the root: low. Restart: affected = upstream BFS + their journeys; high if the
service is in the top 20 % by betweenness or uses a stateful store (the cart cache). Paging: no risk.

**How do you know the fix worked?**
`verify.watch`: every alert in the incident must stay resolved for 3 ticks within 150 s; then the action is verified,
the incident resolved and the report written. Otherwise it reports failure and proposes the next option.

**How does memory work?**
Each incident links to `SignalPattern` nodes (`node:kind`). `similar_incidents` computes Jaccard overlap with resolved
incidents (+0.1 if the past root matches). ≥ 0.6 is a strong match and its fix is proposed first.

**How does *Fix it in code* work?**
The GitHub scan stores where each flag is read (`READ_IN {file, line}`). For the root's changed flag, RootCause fetches
that file from the fork, Gemini returns find/replace edits, they apply only if each `find` matches exactly once, and
RootCause opens a PR with the graph's evidence. At most one PR per 10 minutes; it never merges. The code layer explains;
it never changes the ranking.

**How did you evaluate it?**
`chaos/runner.py`: pick a random fault from 16 (seeded), don't tell the engine, wait up to 180 s for a verdict, settle
45 s, score top-1/top-3 against the catalogue truth. Baselines on the same alert snapshot: loudest alarm, first
alarm, highest error rate, graph signals off, and Gemini given only a flat alert table. The scorecard is generated.

**Gemini without the graph also got 80 %. Why does the graph matter?**
They missed different faults: only RootCause found the broken connection (`paymentUnreachable` → `edge:checkout->
payment`). And a guess isn't an answer you can act on: the graph gives the proof path, the change, the impact, the
risk of each fix, the verified recovery and the memory.

**What are the limits?**
If the real cause never raises an alarm, it isn't a candidate (all three misses). Partial faults (10 % ad failures)
are hard. A Kafka flood can create a second incident on the database. The public site is a replay (the live demo needs
~8 GB). The UI is built for desktop.

**What would you do next?**
More change sources (deploys, config pushes), an independent verifier that runs the PR's tests, real paging
(Slack/WhatsApp), multiple systems and tenants (one FalkorDB graph per tenant), and auth for the live mode.
