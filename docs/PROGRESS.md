# Progress

Code for every milestone is written. **No acceptance check has been run yet**: the dev machine had no Docker, so
FalkorDB, the OpenTelemetry Demo and the graph tests could not start. A box is ticked only after its check passes
and the output is pasted below it.

What did run (2026-10-15): `ruff check backend tests scripts` clean; `pytest tests/unit` 46 passed;
`pytest tests/graph tests/scenarios` collected 83 tests, all skipped (no Docker); `npm run build` of the UI succeeded.

| # | Milestone | Code | Acceptance check |
|---|---|---|---|
| M0 | Skeleton, Makefile, compose, settings, FalkorDB, `make seed` | done | [ ] `make up && make seed` → labels/counts show teams + journeys |
| M1 | Demo + collector override, `/v1/traces` receiving | done | [ ] API log shows span batches; collector clean; §5 VERIFY items recorded |
| M2 | Spans → Service, CALLS/CALLED_BY, messaging, USES, journeys | done | [ ] ≥ 12 services + frontend→checkout→payment in FalkorDB Browser; `tests/graph` pass |
| M3 | Metrics, docker stats, flag watcher, docker events | done | [ ] flipping a flag creates a `Change` within 5 s |
| M4 | Baselines, rules, `:Anomalous` | done | [ ] `paymentFailure` → alerts on payment/checkout/frontend within 30 s; off → resolved |
| M5 | BLAMES, WCC, ranking, edge causes, changes, impact, evidence | done | [ ] `paymentFailure` → 1 incident, top-1 payment, change + checkout journey; `paymentUnreachable` → `edge:checkout->payment` |
| M6 | Actions, verify, report | done | [ ] approve revert → incident resolved + report |
| M7 | UI v1 | done (builds) | [ ] M5–M6 flow visible and clickable |
| M8 | MCP, autopilot, LLM agent, Step trail | done | [ ] Claude Desktop answers "who owns payment?"; agent JSON produced; trail visible |
| M9 | Extras: memory, predict, safety, invisible + AI faults | done | [ ] PRD acceptance lines (PRD not in repo yet) |
| M10 | Chaos runner, baselines, scorecard, recorder, golden tests | done | [ ] `make chaos N=15` writes SCORECARD.md; `make scenario-test` green |
| M11 | Replay deployment, docs, README | done | [ ] fresh VM: one command → public URL in REPLAY |

## Open VERIFY items (CLAUDE.md §5) — none checked yet
- [ ] collector exporter type name and `encoding: json`
- [ ] demo Docker network name
- [ ] Prometheus host/port; real metric names via `scripts/discover_metrics.py`
- [ ] flagd file path + hot reload; catalogue variant names
- [ ] agent service host/port for `POST /prompt`; AI flags with `USE_VCR=True`
- [ ] `feature_flag.key` on spans
- [ ] FalkorDB: `SET n:Anomalous` / `REMOVE n:Anomalous`, `SET n += map`, `shortestPath` form (covered by tests/graph)
