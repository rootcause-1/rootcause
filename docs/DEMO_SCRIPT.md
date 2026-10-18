# Demo video script (≤ 3 min)

## Final version (18 Oct): the real run, ending with a real pull request

Everything on screen is the real system on one laptop: the OpenTelemetry Demo shop, RootCause in LIVE mode with the
Gemini agent, our fork on GitHub (`yash4428/opentelemetry-demo`) and the FalkorDB Browser. The public replay site only
appears on the end card. Illustrated version with screenshots: the "RootCause Field Guide" artifact (ask Yash for the link).
~400 spoken words; say the numbers you actually see on screen.

| Time | On screen / you do | Say |
|---|---|---|
| 0:00–0:20 | Cut from scene 5: the map as the alarms light up, title card. | "It's 3 AM. Four alarms go off across two teams. Every alarm is real, but only one service is actually broken, and finding it is the slow part of every outage. RootCause finds it in about a minute, proves it, fixes it with your OK, and opens the code fix as a pull request." |
| 0:20–0:35 | Shop at `localhost:8080` (browse, add to cart), then the RootCause map, all green, LIVE badge. | "This is the official OpenTelemetry Demo: a real online shop with 19 services and live traffic, running on our laptop. Every five seconds RootCause turns its traces and metrics into a live graph in FalkorDB: who calls whom, who owns what, and what just changed." |
| 0:35–0:45 | Codebase tab: paste `https://github.com/yash4428/opentelemetry-demo`, Scan. | "We connect the shop's GitHub repo too, so the graph knows which code runs each service and where every feature flag is read." |
| 0:45–0:58 | `localhost:8080/feature`: `paymentFailure` → `100%`, Save. Place an order: it fails. | "Now a bad config change goes out: the payment-failure flag is set to one hundred percent. Checkout breaks. We don't tell RootCause anything." |
| 0:58–1:20 | Map turns amber; chat "4 alarms… one incident", then "What I'm checking in the graph" fills with Gemini's tool calls. Hover one: the map lights up the nodes it cited. (speed up the wait) | "Alarms fire on payment, checkout, the storefront and the gateway. RootCause sees in the graph that they're connected, so it opens one incident instead of four pages. Its Gemini agent investigates through our MCP tools: it ranks the suspects, traces the evidence and checks what changed." |
| 1:20–1:45 | Payment red, red trail gateway → storefront → checkout → payment; flag change; "The code behind it" → click the `charge.js` line (GitHub opens on it); who hurts; who's on call. | "The root cause is payment. The blame runs through the graph from the gateway down to payment, payment's own requests are failing, and its flag changed a minute before the alarms. RootCause shows the exact line of code that reads that flag, the customers who can't check out, and who's on call." |
| 1:45–2:05 | "Should I fix this?" risk low → **Yes, fix it** → Fixing → All clear. (speed up ~80 s, show "4×") | "It offers the safest fix first: switch the flag back. That's low risk. A restart would be riskier, so it would need typed confirmation. I approve. RootCause applies the fix, waits until every alarm has cleared, and only then marks the incident resolved." |
| 2:05–2:35 | "One more thing… fix it in the code?" → **Yes, open a pull request** → PR link → GitHub: description (root cause, evidence path, change, impact) → Files changed → read it → Merge (or "Review changes" if it looks wrong). | "The flag is off, but the code that failed is still there. RootCause reads that file from GitHub, Gemini writes a change, and RootCause opens a pull request with the evidence from the graph. It never merges or deploys anything itself. A person reviews the change and merges it." |
| 2:35–2:55 | FalkorDB Browser `localhost:3300`, graph `rc_live`, run the query below; then 3 s of the scorecard. | "All of this lives in one FalkorDB graph: services, alarms, the agent's steps, incident memory and the pull request. Connected components group the alarms, PageRank follows the blame, and shortest path gives the proof. In fifteen blind tests with random faults, RootCause named the right cause first eighty percent of the time; blaming the loudest alarm got fifty-three. Gemini with only a table of the alarms also got eighty, but only the graph caught the broken connection, and only RootCause proves the cause and fixes it." |
| 2:55–3:00 | End card: RootCause · http://3.234.90.242/ · github.com/rootcause-1/rootcause · Track 01. | "Next time, it remembers what worked. That's RootCause." |

Scorecard numbers are from batch 4 (18 Oct, `docs/scorecards/batch4_20261018_073532.md`).

```cypher
MATCH (p:PullRequest)-[f:FIXES]->(i:Incident)-[rc:ROOT_CAUSE]->(r)
OPTIONAL MATCH (p)-[c:CHANGES]->(m:CodeModule)
OPTIONAL MATCH (i)<-[po:PART_OF]-(a:Alert)
RETURN p, f, i, rc, r, c, m, po, a
```

**Say these parts carefully (honesty):**
- The flag revert stops the bleeding and recovery is verified before the PR exists. The PR is the follow-up.
- Merging does not change the running shop (it runs prebuilt images). Say "after review, your CI/CD ships it".
- Gemini writes a different change each run: read the diff before merging on camera. PR #1's change only keeps the
  failure for `synthetic_request` traffic, and the demo's load generator marks all its traffic synthetic
  (`src/load-generator/locustfile.py`), so in this demo that exact change would not stop the errors if deployed.
- Why the fork and not a new buggy repo: the hackathon data rule (telemetry from the OpenTelemetry Demo only),
  RootCause only sees services that send it traces, and the fork's fault paths are real code behind feature flags.

**Before recording:** chaos batch finished; `RC_AGENT_MODE=llm` in `.env`;
`docker compose -f infra/docker-compose.yml --env-file .env up -d --no-deps rootcause-api`;
`curl -X POST http://localhost:8000/api/admin/reset`, wait 3 min; optionally close PR #1; open the five tabs
(shop, `/feature`, `localhost:8088`, the fork, `localhost:3300`); Mac plugged in, Do Not Disturb; one rehearsal
(PR cooldown is 10 min). Backup: record the public site's self-running story and use PR #1 for the GitHub part.

## Earlier drafts (15–17 Oct)

### Version 1: graph-first walkthrough

Recorded from the real system: the OpenTelemetry Demo (agentic mode) + RootCause on one laptop, or the public replay
site (same code path, recorded telemetry). Screen: 1920×1080, UI at `localhost:8088` (or the public URL), browser zoom
110 %. Numbers below are from our live runs on 15 Oct 2026; read them off the screen when recording.

**Lead with the best moment**: the storm of alerts collapsing into one incident with a highlighted evidence path.

| Time | Shot | Voice-over (say roughly this) |
|---|---|---|
| 0:00–0:12 | **Cold open.** Incident panel already showing *"4 alerts → 1 incident"*, evidence path glowing yellow on the graph `frontend-proxy → frontend → checkout → payment`. | "Four services are alerting. RootCause says it's one incident, and the cause is payment — here's the proof." |
| 0:12–0:30 | Title card + healthy live graph (LIVE badge, green edges, left→right tiers). | "RootCause is an on-call agent for the OpenTelemetry Demo shop. Every service, call, queue, journey, team, flag change and alert is a node or edge in FalkorDB, updated every five seconds from live traces." |
| 0:30–0:50 | Terminal or Chaos lab: flip `paymentFailure` (Mystery round in Chaos lab hides the name). Edges turn red, nodes pulse. | "Let's break something. The engine isn't told what — it only sees telemetry, and that a flag changed." |
| 0:50–1:15 | Incident card appears (~25–40 s after the flip). Point at the ranked bars: payment 0.90 — depth, self, PageRank, change. | "Alerts are grouped with weakly connected components over BLAME edges. Then five graph signals rank the cause: who has nothing left to blame, who errors on its own, PageRank over blame, a change that affects it, and memory." |
| 1:15–1:35 | Hover the evidence path; open What changed (`paymentFailure off → 100%`) and Journey impact (checkout −78 … −100 %). | "Shortest path over BLAMES is the evidence. The graph knows the flag affects payment because payment evaluates it on its own spans — and the checkout journey is down." |
| 1:35–1:50 | Agent trail: scroll the steps (get_incident → rank_root_causes → evidence path → what_changed → measure_impact → who_owns → propose). Hover a step: cited nodes light up. | "An agent investigates through our MCP server — the same 16 tools Claude Desktop can use. Every step is stored in the graph with the nodes it cited." |
| 1:50–2:10 | Action card: *flag revert paymentFailure — risk low*, restart *risk high* (needs typed `RESTART payment`). Click **Approve**. Status: executed → verified. | "It proposes the lowest-risk fix. Risk comes from the graph: blast radius by BFS, betweenness, stateful stores. A human approves; RootCause executes, then verifies recovery." |
| 2:10–2:25 | Reports tab: the generated report (root cause, confidence, path, change, impact, timeline). | "It writes the post-incident report from the graph." |
| 2:25–2:40 | Break it again. The new incident shows *Similar past incidents: INC-0001 — strong match*, memory bar on payment, past fix proposed first. | "Next time, it remembers: Jaccard over shared signal patterns finds the past incident and its fix." |
| 2:40–2:55 | `docs/SCORECARD.md`: 15 blind runs — RootCause 87 % top-1 / 93 % top-3, median 53 s; graph signals off 80 %; loudest / first / highest-error alert 40 %; the two misses listed. | "Fifteen blind chaos runs on the real demo: 87 percent top-1, against 40 percent for the usual alert heuristics. Turn the graph signals off and it drops. And we list our misses." |
| 2:55–3:00 | URL + repo + "FalkorDB · Track 01: Agents That Act on Connected Data". | "RootCause. Try the replay at the link below." |

### Version 2: "give it your GitHub" (17 Oct)

Needs: our fork of the demo shop (e.g. `rootcause-1/opentelemetry-demo`), `GITHUB_TOKEN` (fine-grained, that fork
only, Contents + Pull requests read/write), `GEMINI_API_KEY`, `RC_PR_REPO=<owner/fork>` in `.env`.

| Time | Screen | Say |
|---|---|---|
| 0:00 | Codebase tab, paste `https://github.com/<owner>/opentelemetry-demo`, click Scan | "This is a real company's code on GitHub: a 20-service online shop in 12 languages. We give RootCause the link." |
| 0:20 | The table fills: services, languages, lines, flag reads; drift section | "It reads the whole codebase into the same FalkorDB graph as the live system: which folder runs as which service, what it depends on, where every feature flag is read." |
| 0:40 | Map tab, Start demo (or Break something → paymentFailure live) | "Now we simulate an incident: someone flips a feature flag in payments." |
| 0:55 | Alarms, one incident, investigating | "Alarms fire on several services owned by different teams. RootCause groups them into one incident with graph algorithms." |
| 1:15 | Root cause + "The code behind it: src/payment/charge.js:40" | "It finds the one real cause, proves it with the evidence path, and points at the exact line of code." |
| 1:35 | Fix popup → Yes, fix it → recovery ticks | "It proposes the safest fix with its side effects, and a person approves it. The alarms clear and recovery is checked." |
| 2:00 | "One more thing… Want me to fix it in the code?" → Yes, open a pull request | "The switch is off, but the bad code is still there. So RootCause asks Gemini to write a small fix…" |
| 2:20 | "Pull request #N is open" → click the link, show the PR on GitHub (diff + description with the evidence) | "…and opens a real pull request on GitHub, with the evidence from the graph. A human reviews and merges it. That's an agent acting on connected data." |

Tip: do one dry run first. The PR cooldown (`code.pr_cooldown_minutes`, 10) blocks a second PR within 10 minutes.

## Recording checklist
- Easiest take: open the public site, click **Start demo** and do nothing: the popups walk through healthy → alarms →
  one incident → root cause → impact → "Should I fix this?" (auto-approves after 12 s) → fixing → back to normal,
  while the map and the failing-requests timeline calm down. Click **Let me decide** to approve by hand on camera.
- Live: `make demo-up && make up`, wait for "Learning baseline" to finish (3 min), all flags off, no open incidents.
- Run the fault from Chaos lab (Mystery round) or `uv run python scripts/acceptance_check.py --flag paymentFailure`.
- Replay alternative: open the public site; the scenario fast-forwards the healthy part and breaks within a minute;
  `POST /api/admin/reset` restarts it.
- Second fault for the "memory" beat: same flag again after the first incident is resolved.
- Keep the AI disclosure honest in the description: built with Claude Code (see `docs/AI_DISCLOSURE.md`).
