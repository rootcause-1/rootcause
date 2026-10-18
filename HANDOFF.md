# Handoff — submission day (18 Oct 2026)

Updated 18 Oct, ~13:00 IST, by Yash (with Claude Code) after pulling and verifying Shambhvi's 17 Oct work.
Read this, then `docs/FEATURES.md` (every feature with its status) and `CLAUDE.md` §0 (rules).

**Deadlines today:** feature freeze **2:00 PM IST** · submission **11:59 PM IST**
(Graph Hacks, FalkorDB, Track 01: *Agents That Act on Connected Data*).
**After 2 PM: no new features.** Only the video, docs, the scorecard sync and bug fixes.

---

## 1. Where things stand (all on `main`, verified today)

| What | State today | Evidence |
|---|---|---|
| Tests on Docker FalkorDB v4.22.1 | `make lint test` → 205 passed · `make scenario-test` → **7 / 7** | `docs/PROGRESS.md` (18 Oct) |
| Live run on the real OpenTelemetry Demo | works end to end (agentic mode, `LOCUST_USERS=12`) | `docs/PROGRESS.md` M0–M11 |
| Former known miss `productCatalogLockContention` | **fixed live**: top-1 `product-catalog` 0.87, database second 0.75 (Shambhvi's "unchanged database is a symptom" rule) | `docs/PROGRESS.md` (18 Oct), `chaos/catalogue.yaml` |
| Replay recordings | 7 (new today: `productCatalogLockContention`) | `replay/` |
| Public demo | **http://3.234.90.242/** now opens on the lock-contention story ("alarms on 5 services, 2 teams, 1 cause"); redeploys itself from `main` | `docs/DEPLOY.md` |
| Connect your GitHub | works live and on the public site (scans the demo repo on start: 37 modules, 26.5k lines, flag reads with file:line) | `docs/PROGRESS.md`, README |
| UI | Shambhvi's company map (customers → team lanes → shared infra) + WhatsApp-style chat narrator, **Start demo** runs the whole story by itself | `frontend/src/components/` |
| Blind chaos scorecard | batch of 15 **running now** on Yash's laptop (started 12:45, ~3 h); last finished batch (16 Oct): 87 % top-1 / 93 % top-3 | `docs/SCORECARD.md`, `docs/scorecards/` |
| Fix it in code (Claude writes a fix, opens a PR) | built and tested with fakes; **not run for real** (needs a fork + keys, see §2.4) | `docs/FEATURES.md` |

Remaining honest weak spots (fine to mention in the video or README): `kafkaQueueProblems` floods the database, which
forms its own incident; the UI is built for laptop/desktop, not phones; the pager list reads a file, not the graph.

---

## 2. What is left today, in order, with an owner

### 2.1 Video (≤ 3 min) — the one thing judges need most. Owner: Shambhvi (Windows) or Yash (screen recording)
- **Option A, Shambhvi's pipeline** (Windows: built-in TTS voices + Playwright + ffmpeg):
  `pip install playwright imageio-ffmpeg && playwright install chromium`, then
  `.venv/Scripts/python video/make_video.py` → `video/out/rootcause-demo.mp4`. It records the **public site**
  ("Start demo") and narrates from `video/script.json`. The demo lines were updated today to the
  lock-contention story the site now plays. **Before running, update `proof_1`** in `video/script.json` with the
  new scorecard numbers (§2.2) if they change; until then it says 87 % / 53 s / 40 % (batch 3, still true).
- **Option B, by hand**: open http://3.234.90.242/, click **Start demo**, screen-record at 1080p, narrate with
  `docs/DEMO_SCRIPT.md`.
- Upload (YouTube unlisted is fine), then replace `_TODO: add YouTube link_` in `README.md`.

### 2.2 Scorecard — Owner: Yash (Claude is watching the batch)
When `make chaos` finishes (~15:45 IST): the API regenerates `docs/SCORECARD.md`; archive it to `docs/scorecards/`,
run `uv run python scripts/sync_readme_scorecard.py`, add a row to the batch table in `docs/PROGRESS.md`, commit.
Never type the numbers by hand. If the batch fails, the 16 Oct numbers already in README stay valid.

### 2.3 README final pass — Owner: both, 10 minutes
- `## Team`: both of you check the draft (who did what) and delete the "_Both: edit…_" line.
- Video link (2.1). Everything else in README is current as of today (screenshot, status, features, scorecard).

### 2.4 Optional: Fix it in code, for real — Owner: whoever has the keys. Skip if short on time.
1. Fork https://github.com/open-telemetry/opentelemetry-demo into `rootcause-1`.
2. Fine-grained GitHub token for **that fork only** (Contents + Pull requests read/write).
3. On the AWS host `.env` (Yash, SSH): `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `RC_PR_REPO=rootcause-1/opentelemetry-demo`,
   `RC_CODE_REPO=https://github.com/rootcause-1/opentelemetry-demo`, then `scripts/deploy_aws.sh`.
Without keys the chat simply does not offer the pull request; nothing breaks.

### 2.5 Optional: Claude Desktop check (closes M8) — Owner: anyone with Claude Desktop, 5 minutes
README "Use it from Claude Desktop" snippet → ask "Who owns payment?" → paste the answer under M8 in PROGRESS.

### 2.6 Submit (before 11:59 PM IST) — Owner: Yash
Repo https://github.com/rootcause-1/rootcause · live URL http://3.234.90.242/ · video link · Track 01.

### 2.7 After judging — Owner: Yash
Terminate the AWS instance and release the Elastic IP (`docs/DEPLOY.md`), ~$12/month otherwise.

---

## 3. Run it

| Want to… | Do |
|---|---|
| Just look | http://3.234.90.242/ → **Start demo** (or wait; it plays and restarts by itself) |
| Work on the UI, no Docker | `cd frontend && npm install && RC_API=http://3.234.90.242 npm run dev` → http://localhost:5173 |
| Replay stack locally (~1 GB) | `make replay-up` → http://localhost:8088 |
| Live on the real demo (~8 GB) | `uv sync && cp .env.example .env && make demo-up && make up && make seed` → http://localhost:8088, wait 3 min |
| Break one fault by hand | `uv run python scripts/acceptance_check.py --flag paymentFailure --approve` |
| Record a scenario | `make record SCENARIO=<flag>` (~10 min), then `make scenario-test` |
| Fresh graph | `POST /api/admin/reset` (live: re-learns baselines for 3 min) |

Graph tests run against any FalkorDB: Docker (default) or `FALKORDB_TEST_HOST/PORT` (e.g. falkordblite in WSL).

---

## 4. Map of the code (new on 17 Oct in **bold**)

```
backend/rootcause/
  ingest/   otlp · spans (window → calls, routes, journeys, flag evals) · pipeline · prom · docker_stats · flag_watcher · tick
  detect/   rules (alert rules, no-data, hysteresis) · baselines (EWMA on graph nodes)
  engine/   core (BLAMES → WCC → ranking) · ranking (**passive_targets: unchanged DB = symptom**) · edge_cause · changes
            impact · evidence · predict · safety · memory
  actions/  service (propose/approve/execute, **runbook automations**, **fix PR**) · flagd · containers · pager · verify · report
  **codebase/** scan (repo → CodeModule/IMPLEMENTS/DECLARES/READ_IN) · store · repo · github · fix (Claude writes the patch)
  **company.py** teams / on-call / journeys / runbooks edited in the graph (Your company tab)
  agent/    autopilot (default, now with a read_code step) · loop (LLM over MCP) · trail
  mcp_server/ server (16 tools) · chaos/ runner · baselines · scorecard · catalogue.yaml · replay/ recorder · player
  graph/queries/*.cypher  (102 named queries; docs/QUERIES.md is generated)
frontend/src/  App · components/ServiceMap (company map) · Narrator (chat) · HealthStrip · tabs/ ChaosLab · Predict ·
               Memory · Reports · **Codebase** · **Company**
video/         make_video.py · scenes.html (explainer) · script.json (narration) · tts.ps1 (Windows TTS)
infra/         docker-compose.yml (live) · docker-compose.replay.yml (public; default scenario productCatalogLockContention)
               autodeploy/ (timer on the AWS host)
```

---

## 5. Deploying

**Pushing to `main` deploys the public site** within ~2 minutes (systemd timer on the host pulls `origin/main`,
rebuilds, restarts only changed images). Check: `curl http://3.234.90.242/api/status`.
SSH (`scripts/deploy_aws.sh`) needs Yash's key and his current IP in the security group (updated today to
122.162.150.68; if Yash's network changes, update the `sg-01d69975e16ac41a3` port-22 rule).

---

## 6. Rules (CLAUDE.md §0)

- FalkorDB is the only database; every query is a named `.cypher` file (`make queries-doc` after adding one).
- The engine never reads the flagd config or the catalogue to decide a cause. No flag-specific code.
- Scorecard numbers are generated (`make chaos`, `scripts/sync_readme_scorecard.py`), never typed.
- One line in `docs/AI_DISCLOSURE.md` per module changed; `make lint test` before every commit;
  `make scenario-test` after any detection/engine change.

---

## 7. Gotchas

- **Lid open, plugged in** during live runs: a sleeping Mac pauses Docker and corrupts runs.
- Docker Desktop must be running for graph tests; without it they *skip* (85 passed, 120 skipped looks green but isn't).
- Rebuild one service with `--no-deps`, or compose restarts the API and it re-learns baselines.
- After detection changes, `POST /api/admin/reset` for clean baselines.
- `LOCUST_USERS=12` (set by `make demo-up`); `productCatalogFailure` is switched via its targeting rule;
  `emailMemoryLeak` is scored at 1000x.
- During lock contention the `astronomy-db` *container* can open a separate one-alert memory incident ~45 s in;
  the main incident is unaffected.
- The public site restarts its scenario after 3 unattended loops (~10 min) so visitors always see a clean story.
- Hard-reload if the browser shows an old UI. More on every rule: `docs/ARCHITECTURE.md`.
