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
| M5 | BLAMES, WCC, ranking, edge causes, changes, impact, evidence | done | [ ] `paymentFailure` → 1 incident, top-1 payment, change + checkout journey; `paymentUnreachable` → `edge:checkout->payment` |
| M6 | Actions, verify, report | done | [ ] approve revert → incident resolved + report |
| M7 | UI v1 | done (builds) | [ ] M5–M6 flow visible and clickable |
| M8 | MCP, autopilot, LLM agent, Step trail | done | [ ] Claude Desktop answers "who owns payment?"; agent JSON produced; trail visible |
| M9 | Extras: memory, predict, safety, invisible + AI faults | done | [ ] PRD acceptance lines (PRD not in repo yet) |
| M10 | Chaos runner, baselines, scorecard, recorder, golden tests | done | [ ] `make chaos N=15` writes SCORECARD.md; `make scenario-test` green |
| M11 | Replay deployment, docs, README | done | [ ] fresh VM: one command → public URL in REPLAY |

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
