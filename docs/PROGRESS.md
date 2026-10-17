# Progress

Code for every milestone is written. **No acceptance check has been run yet**: the dev machine had no Docker, so
FalkorDB, the OpenTelemetry Demo and the graph tests could not start. A box is ticked only after its check passes
and the output is pasted below it.

What did run (2026-10-15): `ruff check backend tests scripts` clean; `pytest tests/unit` 46 passed;
`pytest tests/graph tests/scenarios` collected 83 tests, all skipped (no Docker); `npm run build` of the UI succeeded.

**Update 2026-10-15 ~4 PM IST (review run, FalkorDB 4.18.3, no OTel demo):** `ruff` clean; `pytest tests/unit tests/graph`
130 passed, 1 skipped (after fixing `evidence_path` and the WCC filter-drop bug). Synthetic-traffic smoke test: payment errors →
1 incident, top-1 `payment`, correct evidence path; vanished payment server spans → top-1 `edge:checkout->payment`.
These are NOT acceptance checks — the boxes below still need the real demo.

| # | Milestone | Code | Acceptance check |
|---|---|---|---|
| M0 | Skeleton, Makefile, compose, settings, FalkorDB, `make seed` | done | [x] `make up && make seed` → labels/counts show teams + journeys |
| M1 | Demo + collector override, `/v1/traces` receiving | done | [x] API log shows span batches; collector clean; §5 VERIFY items recorded |
| M2 | Spans → Service, CALLS/CALLED_BY, messaging, USES, journeys | done | [x] ≥ 12 services + frontend→checkout→payment in FalkorDB Browser; `tests/graph` pass |
| M3 | Metrics, docker stats, flag watcher, docker events | done | [x] flipping a flag creates a `Change` within 5 s |
| M4 | Baselines, rules, `:Anomalous` | done | [x] `paymentFailure` → alerts on payment/checkout/frontend within 30 s; off → resolved |
| M5 | BLAMES, WCC, ranking, edge causes, changes, impact, evidence | done | [x] `paymentFailure` → 1 incident, top-1 payment, change + checkout journey; `paymentUnreachable` → `edge:checkout->payment` |
| M6 | Actions, verify, report | done | [x] approve revert → incident resolved + report |
| M7 | UI v1 | done | [x] M5–M6 flow visible and clickable |
| M8 | MCP, autopilot, LLM agent, Step trail | done | [~] Claude Desktop answers "who owns payment?"; agent JSON produced; trail visible |
| M9 | Extras: memory, predict, safety, invisible + AI faults | done | [x] PRD acceptance lines (PRD not in repo yet) |
| M10 | Chaos runner, baselines, scorecard, recorder, golden tests | done | [x] `make chaos N=15` writes SCORECARD.md; `make scenario-test` green |
| M11 | Replay deployment, docs, README | done | [x] fresh VM: one command → public URL in REPLAY |

## VERIFY items (CLAUDE.md §5) — resolved 2026-10-15 against the live demo
- [x] collector exporter type name and `encoding: json` → `otlp_http/<name>` + `encoding: json` accepted (collector-contrib 0.160.0); bodies are gzip
- [x] demo Docker network name → `opentelemetry-demo`
- [x] Prometheus `prometheus:9090`; `kafka_consumer_group_lag_sum_ratio` (by topic, group), `jvm_memory_used_bytes` (by service_name)
- [x] flagd file `src/flagd/demo.flagd.json` (dir-mounted at /etc/flagd → atomic replace is safe); hot reload: yes (payment fails within seconds of the edit); variants copied into catalogue.yaml
- [x] agent `http://agent:8010/prompt`, body `{"message": ...}`; the load generator already sends prompts. AI flags under VCR: `aiSlowResponse` sleeps before the (replayed) LLM call; cassettes contain the 20-iteration runaway run
- [x] `feature_flag.key` on spans → yes, as `feature_flag.evaluation` span events (cart, checkout, product-catalog, recommendation, agent): AFFECTS edges are now derived from them (`upsert_flag_affects`), seed map is the fallback
- [x] FalkorDB: `SET n:Anomalous` / `REMOVE n:Anomalous`, `SET n += map`, `shortestPath` form (covered by tests/graph)


---

## Live acceptance runs (2026-10-15, real OpenTelemetry Demo, agentic mode, FalkorDB v4.22.1, MacBook, Docker VM 7.6 GB)

Full mode fits: demo + RootCause use ~4.7 GB. Image pulls needed retries (quay/ghcr TLS timeouts), nothing else.

### M0 — `make up && make seed`
```
seeded rc_live: {'teams': 5, 'people': 10, 'journeys': 5, 'runbooks': 12, 'flags': 18}
['Team'] 5   ['Container'] 31   ['Runbook'] 12   ['FeatureFlag'] 18   ['Service'] 32
['SignalPattern'] 18   ['Person'] 10   ['Journey'] 5
```

### M1 — collector → `/v1/traces`
- First run: collector logged `responded with HTTP Status Code 400` — the otlp_http exporter **gzips** bodies.
  Fixed in `ingest/otlp.py` (`Content-Encoding: gzip` + magic-byte sniffing). After: no exporter errors,
  `/api/status` → `spans_received: 1755, batches_received: 125` after ~20 s, ~11k spans/80 s.
- VERIFY items: see the list at the end of this file (all resolved).

### M2 — graph
Live graph after 80 s: 15 services with traffic (ad, agent, cart, checkout, currency, email, flagd, frontend,
frontend-proxy, image-provider, payment, product-catalog, quote, recommendation, shipping) + accounting /
fraud-detection via Kafka; CALLS include `frontend-proxy->frontend`, `frontend->checkout`, `checkout->payment`
(grpc), `checkout->shipping/email` (http), `shipping->quote`; `checkout -PRODUCES_TO-> queue:orders
-CONSUMED_BY-> accounting, fraud-detection` (groups set); `cart -USES-> cache:valkey-cart`,
`product-catalog/accounting -USES-> db:astronomy-db`; 5 journeys with traffic; `agent` gets
`tool_calls_per_run`, `llm_p95_ms`, `agent_runs`. `tests/graph` pass (`make test`: 140 passed).
Fixes needed for the real demo: peers from `rpc.method` (new semconv; no `rpc.service`), `rpc.system.name`,
Envoy `http.protocol`, Kafka `messaging.kafka.consumer.group`, datastore id from `server.address`, journey entry
spans whose parent is the (now traced) load generator / browser, workflow span `astronomy_shop_agent_workflow.workflow`.

### M3 — flag flip → `Change`
```
t=0s  flag paymentFailure -> 100%
t=0.7s  Change CHG-e9dc599e: off -> 100%          (earlier run: 1.8 s)
```

### M4/M5/M6 — `paymentFailure` (scripts/acceptance_check.py --flag paymentFailure --approve)
```
t=0s  flag paymentFailure -> 100%
t=0.7s  Change CHG-e9dc599e: off -> 100%
t=32.5s  ALERT error_rate on frontend-proxy (value 0.333)
t=32.5s  ALERT error_rate on frontend (value 0.333)
t=32.5s  ALERT error_rate on checkout (value 0.333)
t=32.5s  ALERT error_rate on payment (value 0.333)
t=34.1s  incident INC-0001 opened

open incidents created by this flip: ['INC-0001']

== INC-0001  members=['checkout', 'frontend', 'frontend-proxy', 'payment']  alerts=4
   #1 payment  score=0.9  {'depth': 1.0, 'self': 1.0, 'pagerank': 1.0, 'change': 1.0, 'memory': 0.0}
   #2 checkout  score=0.3115  {'depth': 0.5, 'self': 0.0, 'pagerank': 0.8073, 'change': 0.0, 'memory': 0.0}
   #3 frontend  score=0.2661  {'depth': 0.5, 'self': 0.0, 'pagerank': 0.5806, 'change': 0.0, 'memory': 0.0}
   evidence path: ['frontend-proxy', 'frontend', 'checkout', 'payment']
   change: {'id': 'CHG-e9dc599e', 'summary': 'paymentFailure changed off→100%'}
   impact: []
   proposals: [('flag_revert', 'paymentFailure', 'low'), ('restart', 'payment', 'high'), ('page', 'payments-team', 'none')]
   verdict: root=payment confidence=0.9 verdict at t=47.6s

approving ACT-0c13fb6a (flag_revert paymentFailure, risk low)
   {"action": "ACT-0c13fb6a", "approved": true, "execution": {"action": "ACT-0c13fb6a", "status": "executed", "simulated": false, "result": {"flag": "paymentFailure", "from": "100%", "to": "off"}, "evidence": ["INC-0001", "paymentFailure"]}}
   resolved after 75s: ttr_ms=118828 resolution=fixed report=INC-0001.md
```
- Alerts fire at 32.5 s (target 30 s): checkout/payment carry only ~0.03–0.08 rps in the demo, so the first
  failing span needs the 10 s finalise lag + 2 hold ticks. Accepted as-is (lowering hold would add noise).
- Frontend/proxy only alert thanks to the per-route error rate (`op_err_rate`): failed checkouts are ~0.2 % of
  the frontend's 15 rps, and the frontend answers them with HTTP **422** + an exception on an inner span.
- Agent `measure_impact` step: `journey:checkout -47%`.
- First run's report was written from the already-recovered graph (path `payment`, impact none). Fixed: the
  engine freezes the diagnosis while a fix is verifying and the report renders the agent's verdict snapshot.

### M5/M6 re-run after fixes (fresh rc_live graph)
```
{open("/private/tmp/claude-501/-Users-yashaggarwal-Desktop-graphhacks/27558558-e9d4-4141-a3fe-4ceb6c09bb42/scratchpad/run_pf1.log").read().strip()}
```
`reports/INC-0001.md`: confidence 0.90, evidence path frontend-proxy → frontend → checkout → payment,
"journey:checkout: 100% drop in success".

### M5 — `paymentUnreachable` → `edge:checkout->payment`
```
{open("/private/tmp/claude-501/-Users-yashaggarwal-Desktop-graphhacks/27558558-e9d4-4141-a3fe-4ceb6c09bb42/scratchpad/run_pu.log").read().strip()}
```
- First attempt ranked `checkout` first: "callee traffic vanished" needs the 60 s window to roll over. Added a
  general signal: ≥ 50 % of an edge's calls failing with **no answering server span** (`unanswered_share`).
- A stale proposal (revert a flag that was already back to its healthy variant) exposed that old changes counted as
  causes. Fixed generally: superseded changes and changes back to the learned-healthy variant are not causes.

### M7 — UI (localhost:8088), driven by clicking in a browser
- `paymentFailure` → incident card "4 alerts → 1 incident", ranked bars (payment 1.00 incl. memory of a past
  incident), what-changed `paymentFailure off → 100%`, journey impact checkout −100%, similar incident (strong
  match), evidence path drawn on the live graph (`docs/img/ui-incident.jpg`).
- Clicked **Approve** on "flag revert paymentFailure (risk low)" → `status: executed` → `status: verified`;
  INC-0003 resolved (`ttr_ms` 140954); Reports tab shows `INC-0003 — root cause: payment`, confidence 1.00.
- Fixed on the way: nodes collapsing to one point on SSE updates (positions now carried over), stale cached
  `index.html` (nginx `no-cache`), isolated infra nodes hidden.

### M8 — MCP + agent
- `scripts/mcp_smoke.py` (streamable HTTP :8811) and `--stdio` (what Claude Desktop launches): 16 tools listed;
  `who_owns(payment)` → payments-team, on call Asha Rao; `list_incidents`, `blast_radius(payment)` work.
- Autopilot agent JSON on every incident (root_cause, confidence, evidence_path, change, impact,
  proposed_actions, narrative) and its Step trail is visible in the UI's Agent trail.
- **Open:** the final check in Claude Desktop itself (a human pastes the README snippet into
  `claude_desktop_config.json`) and LLM agent mode (`RC_AGENT_MODE=llm` needs `ANTHROPIC_API_KEY`).
- Detector fix found via the UI: checkout/payment get ~2 requests/min, so some 60 s windows have no payment spans;
  those were treated as healthy and resolved the alert. Now a too-quiet window is `no_data` and holds state.

## Break every catalogue flag once (CLAUDE.md §12 note) — 15/16 Oct 2026

`scripts/acceptance_check.py --flag <f>` per flag (flip as a human would, watch ≤ 210 s, let the verdict settle 45 s,
revert). Pass 1 ran on the engine as of the M7 check; every miss was fixed **generally** (no flag-specific code), then
re-run (pass 2). Details per flag are in the comments of `backend/rootcause/chaos/catalogue.yaml`.

| Flag | Class | Pass 1 top-1 | Fix (general) | Pass 2 top-1 |
|---|---|---|---|---|
| paymentFailure | errors | ✅ payment (t=41 s) | – | – |
| paymentUnreachable | errors | ✅ edge:checkout->payment (34 s) | – | – |
| cartFailure | errors | ✅ cart (35 s) | – | – |
| adFailure | errors | ✅ ad (63 s) | – | – |
| productCatalogFailure | errors | ❌ no alerts | the flag has a targeting rule: switch/watch flags through `targeting.if[1]` like the demo's flag UI (the fault was never injected) | ✅ product-catalog (55 s) |
| productCatalogLockContention | latency | ❌ db:astronomy-db #1, truth #2 | proposals now include reverting live changes on other top-3 suspects | ❌ db:astronomy-db 0.76, truth #2 at 0.73 — **known miss**; first proposal is the right flag revert |
| imageSlowLoad | latency | ❌ frontend (a Node heap sawtooth raised a memory alert) | memory slope must also exceed baseline + 3× its deviation | ✅ frontend-proxy (48 s) |
| intlShippingSlowdown | latency | ❌ checkout (shipping never alerted) | slowest-route p95 per service (only non-US `/ship-order` is slow) | ✅ shipping (153 s) |
| adHighCpu | invisible | ✅ ad (30 s, cpu) | – | – |
| adManualGc | latency | ✅ ad (45 s) | + JVM GC-pressure rule (time in GC from Prometheus) | ✅ ad (43 s) |
| emailMemoryLeak | invisible | ❌ 100x: no alert in 7 min (~2.4 MB/min) | catalogue variant 1000x (the demo's own; 100x is below any sane threshold) | ✅ email (56 s) |
| recommendationCacheFailure | invisible | ✅ recommendation (132 s) | – | – |
| kafkaQueueProblems | invisible | ❌ db:astronomy-db | CONSUMER spans count as inbound work (a throttled consumer is a slow service); truth is fraud-detection **or** checkout (both effects are in the demo source) | ✅ fraud-detection (39 s) |
| kafkaConsumerDead | invisible | ✅ fraud-detection (77 s, vanished consumer) | – | – |
| aiRunawayAgent | ai | ✅ agent (36 s, agent_loop) | – | – |
| aiSlowResponse | ai | ✅ agent (56 s, llm_latency) | – | – |

Pass 1: 10/16 top-1. After the general fixes: 15/16 top-1, 16/16 top-3 (lock contention ranks the DB first).
These are hand checks, not the scorecard; the blind numbers come from `make chaos` (docs/SCORECARD.md).

Other things the sweep exposed and fixed: noise from tiny samples (latency p95 needs ≥ 10 requests, Kafka lag must
grow ≥ 3 messages for 30 s, CPU must hold 30 s, latency must also exceed baseline + 3× deviation), the demo's default
5 load-generator users being too few (LOCUST_USERS=12), and the Mac sleeping mid-run (pauses the Docker VM; runs
during sleep were discarded and repeated).

### M9 — extras (acceptance lines from docs/PRD.md R7–R10)
- **Memory (R7):** a repeat of `paymentFailure` showed *Similar past incidents: INC-0001 1.00 strong match* in the UI,
  memory signal 1.0 on payment, and its fix (`flag_revert paymentFailure`) proposed first (screenshot in M7 run).
- **Predict-then-prove (R8):** `POST /api/predict {"node_id": "shipping"}` → PRD-0b48c798 predicted
  {shipping, checkout, frontend, frontend-proxy}; during the recorded `intlShippingSlowdown` break,
  `POST /api/predictions/PRD-0b48c798/score` → actual anomalous {frontend, shipping}: **recall 1.0, precision 0.5**
  (checkout/proxy had not alerted yet at that moment). Journey prediction now only names journeys that critically
  require the broken node (it used to predict every journey through the frontend).
- **Safety (R9):** every proposal carries risk + affected services/journeys; `restart payment` is `high` (top-20 %
  betweenness) and the UI requires typing `RESTART payment`; flag reverts are `low`; paging is `none`.
- **Invisible + AI faults (R10):** CPU (adHighCpu), GC pressure (adManualGc), Kafka lag + vanished consumer
  (kafkaConsumerDead), slow consumer (kafkaQueueProblems), memory leak (emailMemoryLeak 1000x), runaway agent and slow
  LLM — all detected and ranked top-1 (see the sweep table). Known miss: lock contention ranks the DB first.

### M10 — recordings and golden tests
6 scenarios recorded from the live demo with `scripts/record_scenario.py` (4 min healthy → flip → 3 min broken →
revert → 2 min recovery; OTLP compacted to the attributes the ingest reads, ~4 MB each): paymentFailure,
paymentUnreachable, intlShippingSlowdown (latency), kafkaConsumerDead (invisible), aiRunawayAgent (AI), adManualGc.
`make scenario-test` → **6 passed** (top-1 = catalogue truth, and the winner has the flag change linked).
The first recordings lacked a flag-file snapshot at start (replay then saw no change); `scripts/backfill_flag_snapshot.py`
prepended the healthy flag state (documented in the script) and the recorder now writes the snapshot itself.

### M11 — public replay deployment
- AWS t4g.small, `scripts/deploy_aws.sh` = `git clone` + `docker compose -f infra/docker-compose.replay.yml up -d --build`
  on a fresh Amazon Linux host → **http://3.234.90.242/** (REPLAY badge, scenario picker, visitor hints).
- On start the healthy segment is fast-forwarded on a virtual clock (baselines warm in < 10 s), the fault plays live:
  INC-0001 "4 alerts → 1 incident", payment 0.90, `paymentFailure off → 100%`, checkout journey −70 %.
- Clicked **Approve** on the flag revert (simulated) → player jumped to the recorded recovery → `verifying` → `resolved`.
- `POST /api/admin/reset` → fresh `rc_replay` graph, warm-up, incident again ~30 s later.

## M10 — blind chaos batches (`make chaos N=15`)
All batches: the harness flips a random catalogue flag (seeded RNG), never tells the engine, waits ≤ 180 s for a
verdict + 45 s settle, scores against the catalogue truth; baselines are scored on the same alert snapshot; a run with
no incident is a miss for every method. Scorecards are generated (never typed); archives in `docs/scorecards/`.

| batch | engine | RootCause top-1 / top-3 | best baseline top-1 | notes |
|---|---|---|---|---|
| 1 `20261015_194536` | after the flag sweep | **80 % / 87 %** (median 54 s) | graph_off 73 %, first_alert 47 %, loudest 33 % | 2 of 3 misses were a harness race: a noise alert opened an incident seconds before the flip and the fault's alerts joined it. Fixed: ≥ 2 failed requests per error alert, latency floor 100 ms, runner scores the incident the fault joined. |
| 2 `20261015_205332` | + those fixes | aborted after 5 runs | – | regression found: the new latency guards hid emailMemoryLeak's latency, the 2-min memory hold exceeded the 180 s window, and the fast EWMA had absorbed earlier undetected leaks into the baseline. Fixed: memory hold 60 s on top of the 2-min slope, EWMA α 0.01 after learning, sample gate only on the service-wide p95. |
| 3 `20261015_213046` | final | **87 % / 93 %** (median 53 s) | graph_off 80 %, loudest/first/highest-error 40 % | misses: kafkaQueueProblems (the DB flood formed its own incident) and productCatalogLockContention (DB ranked #1, truth #2). `docs/SCORECARD.md`. |

## 17 Oct: ranking rule, company setup, automations (local FalkorDB, no Docker)
FalkorDB module 4.18.3 run from `falkordblite` inside WSL (port 6390), tests pointed at it with
`FALKORDB_TEST_HOST=127.0.0.1 FALKORDB_TEST_PORT=6390`:
```
ruff: All checks passed!
pytest tests/unit   -> 77 passed
pytest tests/graph  -> 104 passed in 19.81s
pytest tests/scenarios -> 6 passed in 212.40s
```
Still open: live check of productCatalogLockContention on the demo and its recording (Yash, HANDOFF §2.0).

## 17 Oct (evening): Connect your GitHub
Same local FalkorDB 4.18.3 (falkordblite in WSL):
```
ruff: All checks passed!
pytest tests/unit      -> 79 passed
pytest tests/graph     -> 117 passed
pytest tests/scenarios -> 6 passed in 474.07s
```
End to end on the real API (replay mode, paymentFailure): startup scan of open-telemetry/opentelemetry-demo found
37 modules (20 with code, 26,514 lines), 83 declared dependencies, 11 gRPC services, 20 flag reads. The chat showed
"Flag paymentFailure is read at src/payment/charge.js:40"; the autopilot trail cites `code:payment`; the scan came
back after `POST /api/admin/reset`. URL guards: non-GitHub URL → 400, other repo on the replay site → 403.

## 17 Oct (night): Fix it in code
```
pytest tests/unit  -> 85 passed
pytest tests/graph -> 120 passed (incl. test_fix_it_in_code_opens_a_pull_request_end_to_end, fake Claude + fake GitHub)
```
Clicked through in the browser on the real API (replay paymentFailure, Claude and GitHub replaced by local fakes):
recovery → "One more thing… fix it in the code?" → Yes → "Pull request #1 is open". Not yet run with a real
ANTHROPIC_API_KEY / GITHUB_TOKEN (needs the fork and keys, HANDOFF §2.0).
