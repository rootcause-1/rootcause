# Handoff: Docker testing (for Yash)

Hi Yash, everything in this repo is coded but **nothing has run against Docker yet** (the machine it was written
on has no Docker). Your job is to get it running, fix what breaks, and tick the acceptance checks in
[docs/PROGRESS.md](docs/PROGRESS.md). Rules for the repo are in [CLAUDE.md](CLAUDE.md); read §0 and §12 first.

Feature freeze: **18 Oct, 2:00 PM IST**.

## What's verified so far
- `ruff check backend tests scripts`: clean
- `pytest tests/unit`: 46 passed
- `cd frontend && npm run build`: builds
- `pytest tests/graph` (82 tests) and `tests/scenarios`: **skipped, never run** (they need Docker)

The 73 Cypher queries in `backend/rootcause/graph/queries/` have never touched FalkorDB. Expect some to fail.

## Setup
Needs Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22, and about 8 GB of free RAM (the demo alone uses ~6 GB).

```bash
uv sync                           # Python deps (mcp is pinned <2 on purpose)
cp .env.example .env              # ANTHROPIC_API_KEY is optional (autopilot works without it)
```

## Step 1: graph tests (do this first, ~30 min)
These start a FalkorDB test container themselves; no demo is needed.
```bash
uv run pytest tests/graph -q
```
Fix every failing `.cypher` file before anything else. Likely trouble spots (FalkorDB is not Neo4j):
- `SET n:Anomalous` / `REMOVE n:Anomalous` in `create_alert` / `resolve_alert`
  (fallback if unsupported is in CLAUDE.md §6)
- `SET n += r.props` in `set_node_props`, `set_incident_props`, `set_action_props`
- the `shortestPath` form in `evidence_path` (fallback: `algo.SPpaths`)
- `algo.WCC` / `algo.pageRank` / `algo.betweenness` / `algo.bfs` call signatures
- map literals inside `collect({...})` and `DISTINCT` on maps in `get_incident`

If you change a query's purpose, run `uv run python scripts/gen_queries_doc.py` to refresh `docs/QUERIES.md`.

## Step 2: bring up the demo and our stack
```bash
make demo-up       # clones ../opentelemetry-demo, copies infra/otelcol-config-extras.yml, runs make start-agentic
make up            # falkordb (:6380, browser :3300), api (:8000 + OTLP :4318), mcp (:8811), ui (:8088)
make seed
```
If the demo isn't at `../opentelemetry-demo`, set `DEMO_REPO_ABS` (absolute path) in `.env`; compose paths
are relative to `infra/`.

## Step 3: VERIFY items (write the real values into `config/rootcause.yaml`)
Each is listed in CLAUDE.md §5 and `docs/PROGRESS.md`. Several are guesses right now:
- [ ] Collector logs: is the exporter type `otlp_http` or `otlphttp`, and is `encoding: json` accepted?
      (The API accepts protobuf too, so dropping `encoding` is fine if it isn't supported.)
- [ ] `docker network ls`: is the demo network `opentelemetry-demo`? (compose: `DEMO_NETWORK`)
- [ ] API log shows span batches arriving; `curl localhost:8000/api/status` shows `spans_received` going up
- [ ] Prometheus host/port inside the network; run `uv run python scripts/discover_metrics.py --url ...`
      and fill `prometheus.queries` (Kafka lag, runtime memory)
- [ ] flagd file name in `src/flagd/` (we assume `demo.flagd.json`) and whether hand edits hot-reload
- [ ] Real flag names and variant names → fix `backend/rootcause/chaos/catalogue.yaml`
      (`productCatalogLockContention`, `intlShippingSlowdown`, `kafkaConsumerDead`, `aiRunawayAgent`,
      `aiSlowResponse` are guesses)
- [ ] Agent service URL for `POST /prompt` (read `compose.agent.yaml`); do AI flags work with `USE_VCR=True`?
- [ ] Service names in Jaeger match `config/seed.yaml` (team ownership) and journey routes match the real routes
- [ ] Do spans carry `feature_flag.key`?

## Step 4: acceptance checks M1–M8 (see docs/PROGRESS.md for the exact check per milestone)
Baselines take 3 minutes to learn after the API starts (the UI header counts down).
1. Graph in FalkorDB Browser (localhost:3300): ≥ 12 services, frontend → checkout → payment
2. Flip a flag by hand → a `Change` node within 5 s
3. `paymentFailure` on → alerts on payment/checkout/frontend within 30 s → one incident, top-1 `payment`
4. `paymentUnreachable` → top-1 `edge:checkout->payment`
5. Approve the flag revert in the UI (localhost:8088) → incident resolved, report in `reports/`
6. MCP: point Claude Desktop at the server (README has the config) and ask "who owns payment?"

Paste each check's output under its row in `docs/PROGRESS.md` and tick it. Commit after each green check.

## Step 5: before M10
Break **every** catalogue flag once by hand. In `catalogue.yaml` comments, write which alerts and nodes you saw.
Report any fault RootCause can't see (the CPU, memory, Kafka and AI faults are the most likely). Then:
```bash
make record SCENARIO=paymentFailure    # ~8 min each; record a few key scenarios
make chaos N=15                         # writes docs/SCORECARD.md
make scenario-test
```

## Known deviations from CLAUDE.md
Listed at the bottom of [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): no temperature 0 for Sonnet 5.5,
`journey:` id prefix, the 10%-of-baseline edge-cause check, npm instead of pnpm, `mcp<2`.

## Also missing (not your job, but FYI)
`docs/PRD.md` (needs exporting), the demo video, public replay deployment, README links/team section.
