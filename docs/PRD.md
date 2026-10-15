# RootCause — Product Requirements

> Written from the team's working spec (CLAUDE.md) and what was verified against the live OpenTelemetry Demo on
> 15 Oct 2026. Where this file and CLAUDE.md disagree, CLAUDE.md §16 (current state) wins and a human decides.

**Hackathon:** Graph Hacks: Context for AI Agents (WeMakeDevs × FalkorDB) · **Track 01:** Agents That Act on
Connected Data · **Window:** 15 Oct 2026 00:01 IST → 18 Oct 2026 23:59 IST · **Feature freeze:** 18 Oct 14:00 IST.

## 1. Problem
When one service breaks in a microservice shop, the pager lights up everywhere: the failing service, every caller up
the chain, the edge proxy, the user journeys. On-call engineers lose the first 20 minutes working out which of the
alerts is the *cause* and which are *symptoms*, what changed, who owns it and what is safe to do. Flat dashboards
and alert lists do not encode the one thing that answers those questions: **how the pieces are connected**.

## 2. Users
- **On-call engineer** — wants one incident instead of a storm, a ranked cause with proof, the change that did it,
  who is impacted, and a safe fix they approve with one click.
- **Team lead / SRE** — wants a report, memory of past incidents, and evidence that the tool is right more often
  than simple heuristics.
- **AI assistants (Claude Desktop, our own agent)** — need the same investigation tools over MCP.

## 3. Product
RootCause watches the official **OpenTelemetry Demo** (agentic mode) and keeps a **FalkorDB** graph of services,
calls, queues, datastores, journeys, teams, runbooks, flags, changes, alerts and incidents, updated every 5 s from
live traces, Prometheus and Docker. On an incident it:

1. **Groups** symptom alerts into one incident (`algo.WCC` over BLAMES edges between anomalous nodes).
2. **Ranks** root causes with five graph signals: blame depth, self-errors, PageRank over BLAMES, a recent change
   that AFFECTS the node, and memory of resolved incidents (Jaccard over shared signal patterns).
3. **Proves** it with an evidence path (`shortestPath` over BLAMES) and finds connection faults (`edge:A->B`) when
   calls go unanswered.
4. **Explains** what changed, which user journeys are impacted, who owns it and the runbook.
5. **Proposes** actions ordered by risk (flag revert < restart < page) with a side-effect report (upstream BFS,
   betweenness, stateful stores); a human approves (typed confirmation for high risk).
6. **Executes**, **verifies** recovery (all alerts resolved for 3 ticks), writes a **report** and **remembers** the
   incident for next time.

An agent drives steps 2–6 through an **MCP server** (16 tools); every tool call is a `(:Step)` in the graph that
`CITED` the nodes it used. Autopilot (deterministic) is the default; an LLM agent (Claude) can drive the same tools.

## 4. Non-negotiables (from the hackathon rules)
- FalkorDB is the only database and does the real work; every query is a named `.cypher` file listed in
  `docs/QUERIES.md`.
- Only demo telemetry generated on our machines + the synthetic seed (invented teams/people/runbooks).
- No faked results: no canned diagnoses, the engine never reads the flag→truth mapping or the flagd config to pick a
  cause; the scorecard is generated, never typed.
- README with setup (live + replay), graph model, queries/algorithms, track, video and deployment links;
  AI-assistant disclosure.

## 5. Requirements and acceptance
| # | Requirement | Acceptance (live demo) |
|---|---|---|
| R1 | Ingest traces/metrics/changes into the graph | ≥ 12 services, frontend→checkout→payment chain, Kafka orders queue, journeys; a flag flip creates a `Change` in ≤ 5 s |
| R2 | Detect anomalies with learned baselines | `paymentFailure` → alerts on payment, checkout, frontend within ~30 s; resolved after the fix |
| R3 | One incident per fault, ranked root cause | `paymentFailure` → 1 incident, top-1 `payment`, change linked, checkout journey impacted; `paymentUnreachable` → `edge:checkout->payment` |
| R4 | Act with approval, verify, report | approve the flag revert → incident resolved, `reports/INC-xxxx.md` written |
| R5 | UI | live graph with evidence path, incident panel, action card, agent trail; the R3–R4 flow is clickable |
| R6 | MCP + agent | Claude Desktop answers "who owns payment?"; agent verdict JSON + Step trail per incident |
| R7 | Memory | a repeat of a resolved fault shows a strong match (≥ 0.6) and its past fix is proposed first |
| R8 | Predict-then-prove | what-if on a service predicts failing services/journeys; after breaking it, precision/recall vs the anomalous set is shown |
| R9 | Safety | every proposal carries risk + affected services/journeys; high risk needs typed `RESTART <service>` |
| R10 | Invisible + AI faults | faults without error spans (CPU, memory, Kafka lag, runaway agent, slow LLM) raise their own alerts where the signal exists; misses are reported honestly |
| R11 | Evaluation | `make chaos N=15` blind runs → `docs/SCORECARD.md`: top-1/top-3/median time-to-diagnosis vs loudest-alert, first-alert, highest-error, LLM-without-graph and graph-signals-off baselines, per fault class, with misses |
| R12 | Public demo | replay mode on a public URL, one command on a fresh VM, actions simulated |

## 6. Out of scope
Production auth/multi-tenancy, other databases, Kubernetes, alert integrations beyond a local pager inbox and an
optional webhook, training ML models.

## 7. Success metrics
- Top-1 accuracy on blind chaos runs above every baseline; median time from fault to verdict < 90 s.
- The 3-minute video shows: storm of alerts → one incident → proof → approved fix → verified → remembered.

## 8. Video script
See [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
