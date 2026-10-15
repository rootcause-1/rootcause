# AI-assistant disclosure

Format: `date · module · what Claude Code did · what a human verified`. Humans fill in the last column.

- 2026-10-15 · repo skeleton, Makefile, config/*.yaml, infra/* · Claude Code wrote the initial versions from CLAUDE.md · _to be verified_
- 2026-10-15 · backend/rootcause/graph (client, registry, schema, 73 .cypher queries) · written by Claude Code; not yet run against FalkorDB · _to be verified_
- 2026-10-15 · backend/rootcause/ingest (otlp, spans, pipeline, prom, docker_stats, flag_watcher, tick) · written by Claude Code; span logic unit-tested · _to be verified_
- 2026-10-15 · backend/rootcause/detect (baselines, rules) · written by Claude Code; unit-tested · _to be verified_
- 2026-10-15 · backend/rootcause/engine (blame, grouping, ranking, edge_cause, changes, impact, evidence, predict, safety, memory, core) · written by Claude Code; pure parts unit-tested · _to be verified_
- 2026-10-15 · backend/rootcause/actions, facts.py, tools.py · written by Claude Code · _to be verified_
- 2026-10-15 · backend/rootcause/agent, mcp_server · written by Claude Code · _to be verified_
- 2026-10-15 · backend/rootcause/chaos, replay, api · written by Claude Code · _to be verified_
- 2026-10-15 · frontend/ · written by Claude Code; `npm run build` passes · _to be verified_
- 2026-10-15 · tests/ · written by Claude Code (46 unit tests pass; graph/scenario tests skipped without Docker) · _to be verified_
- 2026-10-15 · docs/ · written by Claude Code · _to be verified_
- 2026-10-15 · graph/queries/evidence_path.cypher, engine/grouping.py (+ blames_count.cypher), ingest/tick.py re-investigation, open_incidents.cypher, chaos/catalogue.yaml truths, scripts/synthetic_traffic.py, CLAUDE.md §15–16 · review + fixes by Claude (claude.ai) after running the graph tests on FalkorDB 4.18.3 and a synthetic end-to-end smoke test · _to be verified_
2026-10-15 · ingest/otlp.py, ingest/spans.py, ingest/pipeline.py, graph/queries/upsert_flag_affects.cypher, config/rootcause.yaml · Claude Code: gzip OTLP bodies, rpc.method/rpc.system.name peer naming, kafka group attr, db id from server.address, journey entry spans under load-generator/browser parents, FeatureFlag-AFFECTS from feature_flag.evaluation span events, verified config values from the live demo · human verified: _
2026-10-15 · detect/rules.py, detect/baselines.py, ingest/spans.py, engine/core.py, actions/report.py, scripts/acceptance_check.py · Claude Code: per-route error rate (op_err_rate), 4xx-with-failing-handler counts as failure, per-kind hold (memory 2 min), LLM latency floor, freeze diagnosis while verifying, report renders verdict snapshot, live acceptance-check script · human verified: _
2026-10-15 · engine/changes (recent_changes_for, set_flag_baselines), ingest/pipeline.py, edge_candidates.cypher · Claude Code: superseded / baseline-restoring flag changes are not causes; edge cause from unanswered call share · human verified: _
2026-10-15 · detect/rules.py, frontend/GraphView.tsx, infra/nginx.conf · Claude Code: NO_DATA state (sparse windows hold alerts instead of resolving them), reuse graph baselines after restart, keep node positions across SSE updates, no-cache index.html · human verified: _
2026-10-15 · replay/player.py, api/main.py, ingest/tick.py, ingest/pipeline.py, tests/scenarios/test_golden.py · Claude Code: replay warm-up on a virtual clock, looping scenarios, POST /api/admin/reset, Pipeline.reset, golden test judges the final diagnosis · human verified: _
2026-10-15 · detect/rules.py, actions/service.py, chaos/runner.py, replay/recorder.py, ingest/otlp.py · Claude Code: variance-aware latency, 30 s lag hold, propose reverts of live changes on top-3 suspects, chaos scores the settled verdict, compact recordings · human verified: _
2026-10-15 · actions/flagd.py, ingest/flag_watcher.py, detect/rules.py, ingest/spans.py · Claude Code: targeting flags switched/watched via their on-branch (as the demo flag UI does), slowest-route p95, GC-pressure rule, variance-aware memory, cpu hold · human verified: _
