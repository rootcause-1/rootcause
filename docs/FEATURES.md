# RootCause: every feature, how it is built, and how FalkorDB is used

Written 17 Oct 2026 for the team (and Yash before he takes over). Status words used below:
**live** = checked against the real OpenTelemetry Demo (docs/PROGRESS.md), **tested** = covered by unit/graph/replay
tests that pass, **new** = written 17 Oct, tests pass but not yet seen on the live demo.

## 1. The product in one paragraph

A shop made of ~15 services breaks. Dozens of alarms fire on many services owned by several teams. RootCause
reads the shop's own traces and metrics into a FalkorDB graph and groups the alarms into one incident. It ranks
the one service that actually broke and shows the chain of blame as proof. It finds the change that caused it
and who is hurt (which customer journeys). Then it proposes the safest fix with its side effects, waits for a
human to approve, applies the fix, checks recovery, writes the report and remembers the incident for next time.

## 2. Feature inventory

### Seeing the system (ingest)
| Feature | How it is built | Status |
| --- | --- | --- |
| Trace ingestion | Collector exports OTLP/HTTP to `POST /v1/traces` (`ingest/otlp.py`, gzip JSON or protobuf). A 60 s span window (`ingest/spans.py`) pairs client/server spans into `CALLS`/`CALLED_BY`, producer/consumer spans into `PRODUCES_TO`/`CONSUMED_BY`, db spans into `USES`, and attributes errors to the service where they start. | live |
| Customer journeys | Root spans matched by route → `Journey` success rate, `REQUIRES {share, critical}` to every service in those traces. | live |
| AI-agent telemetry | Tool calls and LLM latency per agent run → properties on the `agent` service. | live |
| Metrics | PromQL with discovered names only: Kafka lag → `Queue.lag`, JVM memory → `Service` (`ingest/prom.py`). | live |
| Containers | docker stats (CPU, memory, memory slope) → `Container` + `RUNS_IN`; docker events → `Change {kind:'restart'}`. | live |
| Changes | flagd file watcher → `Change {kind:'flag'}` -[:CHANGED]-> `FeatureFlag`; `AFFECTS` edges come from flag-evaluation span events. | live |

### Noticing something is wrong (detect)
| Feature | How it is built | Status |
| --- | --- | --- |
| Learned baselines | EWMA mean + deviation per metric, stored on the graph node/edge itself (`bl_<metric>`), frozen during incidents. | live |
| Alert rules | error rate, latency, lag, memory, CPU, JVM GC, agent loop, LLM latency; each must hold 2 ticks, resolve after 3 (`detect/rules.py`). | live |
| `:Anomalous` label | Firing nodes get the label; every engine query works on that live subgraph. | live |

### Finding the one cause (engine)
| Feature | How it is built | Status |
| --- | --- | --- |
| Blame graph | Every tick: failing caller → failing callee `BLAMES`; lagging queue → its consumer (`rebuild_blames`). | live |
| Many alarms → one incident | `algo.WCC` over BLAMES; ids stay stable by member overlap (`engine/grouping.py`). | live |
| Root-cause ranking | 0.30 depth + 0.25 own errors + 0.20 `algo.pageRank` + 0.15 recent change + 0.10 memory (`engine/ranking.py`). | live, 87 % top-1 in the blind batch |
| "Database is only a symptom" rule | An unchanged database with no resource alarm doesn't count against a changed service that uses it (`blame_targets`). Fixes the lock-contention miss. | new, unit + graph + replay tests |
| Broken connections | Caller fails and callee's traffic vanished → hypothesis `edge:A->B` (`engine/edge_cause.py`). | live |
| Invisible faults | Lagging queue whose consumer went silent → the dead consumer (it raises no alarm itself). | live |
| What changed | Flag changes on `AFFECTS` and container restarts on `RUNS_IN`, timed against onset. | live |
| Business impact | Journeys that `REQUIRE` failing services and how far their success rate dropped. | live |
| Evidence path | `shortestPath` over BLAMES from the customer-facing edge to the root. | live |

### Acting safely (actions)
| Feature | How it is built | Status |
| --- | --- | --- |
| Proposals | memory-backed fix → flag revert → runbook automation → restart → page owner; ordered by risk (`actions/service.py`). | live (automation: new) |
| Side-effect report | Restart blast radius via `algo.bfs` upstream; risk via `algo.betweenness`; stateful if it uses a session store (`engine/safety.py`). | live |
| Approval | Single-use token, 10 min TTL, stored hashed; high risk needs a typed phrase (`RESTART payment`). | live |
| Apply | flagd atomic JSON write; Docker restart; runbook webhook POST; page = inbox + optional Slack/Discord webhook. | live (webhook: new) |
| Verify recovery | All incident alerts resolved within 150 s, else the next fix is proposed. | live |
| Report | Facts from the graph, LLM narration optional; `Report` node + `reports/INC-xxxx.md`. | live |

### Thinking ahead (memory, prediction)
| Feature | How it is built | Status |
| --- | --- | --- |
| Incident memory | Each incident's `SignalPattern` fingerprint; Jaccard similarity to resolved ones; ≥ 0.6 → its fix is proposed first. | live |
| What-if prediction | "If X breaks": `algo.bfs` over `CALLED_BY` (sync calls spread errors upward, Kafka does not) + critical journeys; scored precision/recall after a real break. | live |

### The agent
| Feature | How it is built | Status |
| --- | --- | --- |
| MCP server | 16 tools (read: incidents, ranking, evidence, changes, impact, blast radius, predict, similar, owner, runbook, read-only Cypher; write: propose, execute-with-token, verify, report). stdio for Claude Desktop, HTTP on :8811. | tested with an MCP client; Claude Desktop check open |
| Autopilot | The same investigation as a fixed tool sequence, no LLM. Default. | live |
| LLM agent | Claude picks the tools (12 calls / 90 s budget), can draft but never execute. | needs `ANTHROPIC_API_KEY` |
| Step trail | Every tool call → `Step` -[:NEXT]-> `Step`, -[:CITED]-> the nodes it used. | live |

### Proving it works
| Feature | How it is built | Status |
| --- | --- | --- |
| Chaos lab | Blind runs: random fault flipped by the harness, engine not told; scored against the catalogue afterwards. | live |
| Scorecard | Compared with 5 baselines (loudest alert, first alert, highest error, graph off, LLM without graph); generated, never typed. | live (LLM baseline needs key) |
| Record / replay | Every engine input recorded; played back through the same pipeline; actions simulated. 6 recordings, public site. | live |
| Golden tests | Each recording replayed into a fresh graph; top-1 must equal the truth. | tested |

### Using it (UI and setup)
| Feature | How it is built | Status |
| --- | --- | --- |
| Company map | Customers → services in their team's lane (with who's on call) → shared infrastructure; live traffic dots. | live |
| Chat narrator | WhatsApp-style chat driven by real incident state; "Yes, fix it"; demo autoplay in replay only. | live |
| Tabs | Break something, Predict, Memory, Reports, **Your company**. | live (company: new) |
| Your company | Teams, on-call, ownership, journeys, runbooks + automation URLs, edited in the graph (ingestion reads journey routes from the graph); export seed.yaml. | new |

## 3. Is FalkorDB used properly? Yes. The details:

**It is the engine's working memory, not a cache.** Every tick writes the observed system into the graph and then
reasons over it there: the alerting subgraph (`:Anomalous`), blame edges, incidents, hypotheses, actions, the agent's
steps, memory and chaos runs. Turn FalkorDB off and nothing can group, rank, explain or remember.

**Graph algorithms doing real work** (all in named `.cypher` files, 89 queries in docs/QUERIES.md):
| Question | Algorithm | Query |
| --- | --- | --- |
| Which alarms belong together? | `algo.WCC` | group_incidents |
| Where does the blame flow? | `algo.pageRank` | pagerank_blame |
| Show me the proof | `shortestPath` | evidence_path |
| What else breaks if X breaks? Who does a restart touch? | `algo.bfs` | upstream_bfs |
| How risky is restarting X? | `algo.betweenness` | service_betweenness |
| Have we seen this before? | Jaccard over shared `SignalPattern`s | similar_incidents |

**Checked today (17 Oct) against real FalkorDB** (module 4.18.3 via falkordblite in WSL, no Docker needed):
104 graph tests and all 6 golden replays pass, including the new company setup and blame_targets tests.

**Honest weak spots:**
1. The UI's "pages sent" list reads `data/pager_inbox.jsonl`, not the graph (the graph does have the `Action`).
   Small; could read `Action {kind:'page'}` instead.
2. FalkorDB features we don't use yet: full-text and vector indexes, more algorithms (k shortest paths, community
   detection). The GitHub connector (§5) would use the full-text index.
3. The compose files pin `falkordb/falkordb:v4.22.1`; today's local check ran on module 4.18.3. Yash's Docker
   run covers 4.22.1.

## 4. Verification run today (17 Oct)
- `ruff`: clean. Unit tests: 77 passed. Graph tests on real FalkorDB: 104 passed.
- Golden replays (`tests/scenarios`) on real FalkorDB: 6 passed (all 6 recordings still top-1 = truth with the
  new database rule).

## 5. What could come next

1. **Connect your GitHub (codebase map).** A company pastes its repository URL. RootCause reads the code
   (never runs it) and adds it to the same graph:
   - `(:CodeModule)-[:IMPLEMENTS]->(:Service)` from the compose/k8s build contexts and folder names;
   - `(:Service)-[:DECLARES]->(:Service|:Datastore)` from compose `depends_on` and `*_ADDR` env vars, so the map
     exists before any traffic, and "declared but never called / called but undeclared" drift is a query;
   - `(:RpcService)` from `.proto` files, matched to the `rpc.method` peers we already see;
   - `(:FeatureFlag)-[:READ_IN {file, line}]->(:CodeModule)`: where in the code each flag is read;
   - `(:Commit)-[:TOUCHED]->(:CodeModule)` and `CODEOWNERS` → `(:Team)-[:OWNS]`.

   During an incident the chat can then point at the code, for example "payment is failing; flag `paymentFailure`
   is read in `src/payment/charge.js:NN`; last commit to it was 3 days ago by …". It stays explanation only: it
   never feeds the ranking, so nothing can be tuned to the answer.
   Tried by hand on the official demo repo: its compose file lists the buildable services and their declared dependencies (e.g. checkout →
   cart, currency, email, payment, product-catalog), 10 gRPC services in `pb/demo.proto`, and flag reads in
   `src/payment/charge.js`, `src/cart/.../CartService.cs` and `src/product-catalog/flags`.
2. Deploys as changes: a deploy webhook (or new container image) → `Change {kind:'deploy'}` linked to the service.
3. Approve from Slack: the page message carries Approve/Reject buttons that hit the same token endpoint.
4. Pager history from the graph (weak spot 1).
