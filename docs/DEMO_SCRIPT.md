# Demo video script (≤ 3 min)

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

## Version 2: "give it your GitHub" (17 Oct, the flow the team wants)

Needs: our fork of the demo shop (e.g. `rootcause-1/opentelemetry-demo`), `GITHUB_TOKEN` (fine-grained, that fork
only, Contents + Pull requests read/write), `ANTHROPIC_API_KEY`, `RC_PR_REPO=<owner/fork>` in `.env`.

| Time | Screen | Say |
|---|---|---|
| 0:00 | Codebase tab, paste `https://github.com/<owner>/opentelemetry-demo`, click Scan | "This is a real company's code on GitHub: a 20-service online shop in 12 languages. We give RootCause the link." |
| 0:20 | The table fills: services, languages, lines, flag reads; drift section | "It reads the whole codebase into the same FalkorDB graph as the live system: which folder runs as which service, what it depends on, where every feature flag is read." |
| 0:40 | Map tab, Start demo (or Break something → paymentFailure live) | "Now we simulate an incident: someone flips a feature flag in payments." |
| 0:55 | Alarms, one incident, investigating | "Alarms fire on several services owned by different teams. RootCause groups them into one incident with graph algorithms." |
| 1:15 | Root cause + "The code behind it: src/payment/charge.js:40" | "It finds the one real cause, proves it with the evidence path, and points at the exact line of code." |
| 1:35 | Fix popup → Yes, fix it → recovery ticks | "It proposes the safest fix with its side effects, and a person approves it. The alarms clear and recovery is checked." |
| 2:00 | "One more thing… Want me to fix it in the code?" → Yes, open a pull request | "The switch is off, but the bad code is still there. So RootCause asks Claude to write a small fix…" |
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
