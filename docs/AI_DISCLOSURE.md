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
