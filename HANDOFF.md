# Handoff — where RootCause stands and how to continue

Written 16 Oct 2026 by Yash (with Claude Code). Read this first, then `CLAUDE.md` §0 (rules) and §16 (state).

**Deadlines:** feature freeze **18 Oct, 2:00 PM IST** · submission **18 Oct, 11:59 PM IST**
(Graph Hacks, FalkorDB, Track 01: *Agents That Act on Connected Data*).

---

## 1. Where things stand

Everything below runs and is on `main`. Nothing is half-merged; there are no other branches.

| Area | State | Evidence |
|---|---|---|
| Live integration with the real OpenTelemetry Demo | works end to end | `docs/PROGRESS.md` (M0–M11, outputs pasted) |
| Acceptance checks M0–M7, M9–M11 | pass | `docs/PROGRESS.md` |
| M8 (MCP) | MCP server verified with an MCP client over HTTP and stdio; the **Claude Desktop** check itself is still open | `scripts/mcp_smoke.py` |
| Every catalogue fault broken by hand | 15 / 16 ranked first after general fixes, 16 / 16 in the top three | comments in `backend/rootcause/chaos/catalogue.yaml`, table in `docs/PROGRESS.md` |
| Blind chaos scorecard (15 random faults) | RootCause **87 % top-1 / 93 % top-3**, median 53 s; alert heuristics 40 %; graph signals off 80 % | `docs/SCORECARD.md`, history in `docs/scorecards/` |
| Replay recordings | 6 scenarios recorded from the live demo; `make scenario-test` 6 / 6 | `replay/*.jsonl.gz` |
| Public demo | **http://3.234.90.242/** (AWS, replay mode), redeploys itself from `main` | `docs/DEPLOY.md` |
| UI | self-running demo: full-screen company map (customers → team lanes → infra) with popups that advance on their own; one click on **Start demo** | `frontend/src/components/` |
| Tests | `make lint test` → 162 passed | – |

The two known misses (both honest, both documented): `productCatalogLockContention` ranks the database first and the
real cause second (a general fix is in, see §2.0, waiting for a Docker run); `kafkaQueueProblems` floods the database, which forms its own incident.

---

## 2. What is left (in priority order)

### 0. NEW (17 Oct, Shambhvi + Claude Code), Yash please run on Docker first

The main demo should be the "4 teams, 1 cause" story: `productCatalogLockContention` makes **12 alarms on 6 services
owned by 3 teams** (storefront, payments, data), and they all come from one place. Until now we ranked the database
first (known miss). Three changes are in, **none verified against FalkorDB yet** (no Docker on Shambhvi's laptop):

- **Ranking rule** (`engine/ranking.py passive_targets`, `engine/core.py`, new query `blame_targets.cypher`):
  a database cannot break itself without a change or a resource alarm (cpu / memory / gc) of its own. So when a
  service that changed just before onset blames a database like that, the database does not count as "something further
  to blame" for that service. A real database fault (no upstream change) still ranks the database first. The winning
  hypothesis stores `explains: [db ids]`, and the chat says the database is a symptom. Unit tests reproduce
  the 0.76 vs 0.73 case. This is general: no flag names, nothing read from flagd or the catalogue.
- **Your company tab** (`company.py`, `api/main.py /api/company*`, `frontend/src/tabs/Company.tsx`, 8 new `company_*`
  queries): edit teams, ownership, on-call, journeys (by route) and runbooks in the graph; download as seed.yaml; reset.
- **Runbook automations**: a runbook can have an automation URL plus a declared risk. RootCause then proposes
  "Run automation" for the root service (ordered after flag reverts, before restarts), with the usual approval token;
  execute POSTs the incident JSON to that URL. In replay it is simulated.

Update (later on 17 Oct): steps 1 and 2 below already pass on real FalkorDB 4.18.3 (run without Docker via
falkordblite in WSL; numbers in PROGRESS.md). Re-run them on Docker (v4.22.1) anyway, then do 3 to 5.

Please run, in order, and paste the outputs into `docs/PROGRESS.md`:
1. `make lint test`: graph tests include `test_company_setup_edits_reach_ownership_and_proposals` and the
   `blame_targets` assertion. Fix anything FalkorDB-specific the small way.
2. `make scenario-test`: the 6 golden replays must stay top-1.
3. Live: break `productCatalogLockContention` by hand. Expect top-1 `product-catalog` and the chat line
   "Postgres database looks slow too, but…". Then record it: `make record SCENARIO=productCatalogLockContention`
   (3 min healthy, break, 3 min broken, fix, 2 min recovery) and commit the file in `replay/`.
4. Make it the main demo: set `RC_REPLAY_SCENARIO` default to `productCatalogLockContention` in
   `infra/docker-compose.replay.yml`, add it to the golden scenario tests, and update the catalogue comment (remove "KNOWN MISS").
5. `make chaos N=15` and copy the new numbers into README "Scorecard" (never type them).

1. **Record the demo video** (≤ 3 min) with `docs/DEMO_SCRIPT.md`. Easiest: open the public site, click
   **Start demo** and let it run (~3 min, the fix auto-approves after a countdown). Put the link in `README.md` (search for `TODO: add YouTube link`).
2. **README team section**: Yash wrote a draft; fix it to say who did what (`## Team` in `README.md`).
3. **Claude Desktop check** (closes M8): paste the snippet from README "Use it from Claude Desktop" into
   `claude_desktop_config.json`, with the stack running, and ask "Who owns payment?". Paste the answer into
   `docs/PROGRESS.md` under M8 and tick it.
4. *Optional*: an `ANTHROPIC_API_KEY` in `.env` enables `RC_AGENT_MODE=llm` and the `llm_no_graph` baseline. If you
   add it, re-run `make chaos N=15` so the scorecard includes that column (never type numbers by hand).
5. *Optional polish*: the UI is tuned for laptop/desktop and video, not phones; the Reports/Memory tabs are simple.
6. **After judging**: shut down the AWS instance (commands in `docs/DEPLOY.md`; Yash has the AWS access).

Do not start big new features before the freeze. If something breaks, fix it the general way (no flag-specific code)
and keep `make lint test` and `make scenario-test` green.

---

## 3. Run it

### A. Just look at it (no setup)
Open http://3.234.90.242/. The healthy part of a recorded fault fast-forwards, the fault plays live, approve the
low-risk fix to see recovery. It starts over by itself. `POST /api/admin/reset` restarts it.

### B. Work on the UI against the public site (fastest loop, no Docker)
```bash
cd frontend && npm install
RC_API=http://3.234.90.242 npm run dev        # http://localhost:5173, proxies /api to the public replay site
```

### C. Replay stack locally (Docker, no OTel demo, ~1 GB RAM)
```bash
make replay-up                                 # http://localhost:8088
```

### D. The real thing: live on the OpenTelemetry Demo (Docker, ~8 GB RAM)
```bash
uv sync && cp .env.example .env
make demo-up      # clones ../opentelemetry-demo, installs our collector override, LOCUST_USERS=12, agentic mode
make up           # FalkorDB (:6380, browser :3300), API (:8000), MCP (:8811), UI (:8088)
make seed
open http://localhost:8088                     # wait 3 min while baselines are learned
uv run python scripts/acceptance_check.py --flag paymentFailure --approve   # break, watch, approve, verify
```
Useful while live: `POST /api/admin/reset` (fresh graph, re-learn), `make chaos N=15` (blind batch, ~3 h),
`make record SCENARIO=<flag>` (one recording, ~10 min), `make scenario-test`.

---

## 4. Map of the code

```
backend/rootcause/
  ingest/      otlp.py (OTLP JSON/protobuf, gzip) · spans.py (window → calls, routes, journeys, flag evals)
               pipeline.py (single entry for live + replay) · prom.py · docker_stats.py · flag_watcher.py · tick.py (5 s loop)
  detect/      rules.py (alert rules, hysteresis, no-data) · baselines.py (EWMA on graph nodes)
  engine/      core.py (BLAMES → WCC → ranking) · ranking.py · edge_cause.py · changes.py · impact.py · evidence.py
               predict.py · safety.py · memory.py
  actions/     service.py (propose/approve/execute) · flagd.py · containers.py · pager.py · verify.py · report.py
  agent/       autopilot.py (default) · loop.py (LLM over MCP) · trail.py (Step nodes)
  mcp_server/  server.py (16 tools)
  chaos/       runner.py · baselines.py · scorecard.py · catalogue.yaml (truths + what we saw)
  replay/      recorder.py · player.py (warm-up, loop, give up after 3 unattended loops)
  graph/       queries/*.cypher (76 named queries; docs/QUERIES.md is generated from their headers)
frontend/src/
  components/  ServiceMap.tsx (company map) · Narrator.tsx (popups, auto-advance, fix + countdown) ·
               HealthStrip.tsx (vitals + timeline) · ActionCard.tsx · TrailDrawer.tsx · Inline.tsx
  palette.ts   colours shared by the map and the page
  tabs/        ChaosLab · Predict · Memory · Reports
config/        rootcause.yaml (every threshold, with a comment saying why) · seed.yaml (invented teams/runbooks)
scripts/       acceptance_check.py · record_scenario.py · mcp_smoke.py · deploy_aws.sh · sync_readme_scorecard.py
               backfill_flag_snapshot.py (one-off, documented) · setup_demo.sh
infra/         docker-compose.yml (live) · docker-compose.replay.yml (public) · autodeploy/ (timer on the AWS host)
```

---

## 5. Deploying

**Pushing to `main` deploys the public site** within ~2 minutes (a systemd timer on the host pulls `origin/main`
and rebuilds; only changed images restart). Check it with `curl http://3.234.90.242/api/status`.
SSH access (`scripts/deploy_aws.sh`) needs the key that is only on Yash's laptop; you should not need it.
Host details and teardown: `docs/DEPLOY.md`.

---

## 6. Rules you must keep (from CLAUDE.md §0)

- FalkorDB is the only database; every graph query is a named `.cypher` file (run `make queries-doc` after adding one).
- The engine never reads the flagd config or the catalogue to decide a cause. No flag-specific code.
- Scorecard numbers are generated: `make chaos`, then `uv run python scripts/sync_readme_scorecard.py` for the README.
- Append a line to `docs/AI_DISCLOSURE.md` for every module you (or an AI assistant) change.
- `make lint test` before every commit; `make scenario-test` after any detection/engine change.

---

## 7. Gotchas we learned the hard way

- **Keep the laptop awake, lid open, plugged in** during live runs. A sleeping Mac pauses the Docker VM and silently
  corrupts runs (we lost a sweep this way).
- Rebuild one service with `--no-deps` (`docker compose ... up -d --build --no-deps rootcause-api`), or compose also
  restarts the API and it re-learns baselines.
- After code changes to detection, reset the live graph (`POST /api/admin/reset`) so baselines are clean.
- The demo's default 5 load-generator users are too few (checkout ~2 req/min); `make demo-up` sets 12.
- `productCatalogFailure` is switched through its targeting rule, not `defaultVariant` (we match the demo's flag UI).
- `emailMemoryLeak` is scored at 1000x; 100x never crosses a sane threshold within minutes.
- Browser caching: the UI's nginx sends `no-cache` for `index.html`; if you see an old UI, hard-reload.
- SSH to the AWS host is flaky from some home networks; deploys don't need SSH.
- More detail on every detection rule and why it exists: `docs/ARCHITECTURE.md` ("What the real demo taught us").

---

## 8. Ask for help

Everything the engine decided during the live runs is in the FalkorDB graph (`rc_live`, browser at
http://localhost:3300 when the live stack is up), and every check's raw output is in `docs/PROGRESS.md`.
