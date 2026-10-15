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
| 2:40–2:55 | `docs/SCORECARD.md` (or Chaos lab scorecard): RootCause vs loudest alert, first alert, highest error, and graph signals off — top-1 / top-3 / time to diagnosis, misses listed. | "Blind chaos runs on the real demo. Without the graph signals, accuracy drops — the graph is doing the work." |
| 2:55–3:00 | URL + repo + "FalkorDB · Track 01: Agents That Act on Connected Data". | "RootCause. Try the replay at the link below." |

## Recording checklist
- Live: `make demo-up && make up`, wait for "Learning baseline" to finish (3 min), all flags off, no open incidents.
- Run the fault from Chaos lab (Mystery round) or `uv run python scripts/acceptance_check.py --flag paymentFailure`.
- Replay alternative: open the public site; the scenario fast-forwards the healthy part and breaks within a minute;
  `POST /api/admin/reset` restarts it.
- Second fault for the "memory" beat: same flag again after the first incident is resolved.
- Keep the AI disclosure honest in the description: built with Claude Code (see `docs/AI_DISCLOSURE.md`).
