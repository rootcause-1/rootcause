# Four Alarms, One Cause: An AI On-Call Engineer on a FalkorDB Graph

*We turned live OpenTelemetry traces into a FalkorDB graph so an AI agent can find the one real cause behind an alarm
storm, prove it, fix it with a person's approval, and open the code fix as a pull request. It runs on a ~$12/month
AWS Graviton instance.*

![RootCause: an AI on-call engineer on a FalkorDB graph](https://raw.githubusercontent.com/rootcause-1/rootcause/main/docs/blog/cover.png)

**▶ Demo video:** [youtube.com/watch?v=tws31rPbplE](https://www.youtube.com/watch?v=tws31rPbplE) ·
**Try it:** [3.234.90.242](http://3.234.90.242/) (click **Start demo**) ·
**Code:** [github.com/rootcause-1/rootcause](https://github.com/rootcause-1/rootcause)

## The 3 AM problem

It's 3 AM. Four alarms go off: the website gateway, the storefront, checkout and payment. Two teams get paged.
Every alarm is real, but only **one** service is actually broken. The other three are failing because they depend
on it. Working out which one, by hand, under pressure, is the slowest part of every outage.

We built **RootCause** for [Graph Hacks: Context for AI Agents](https://www.wemakedevs.org/hackathons/falkordb)
(WeMakeDevs × FalkorDB). It watches a real shop, turns everything it sees into a graph, and lets an AI agent find
the cause, prove it, fix it with a person's approval, check that the fix worked, and open the code fix as a pull
request.

## Why a graph

When we wrote down the questions an on-call engineer asks during an outage, every one of them was about
connections. Each one maps to a graph algorithm that [FalkorDB](https://www.falkordb.com/) runs in a single query:

| The on-call question | The graph answer |
|---|---|
| Which of these alarms belong together? | **Connected components** (`algo.WCC`) |
| Where does the blame flow? | **PageRank** (`algo.pageRank`) over "who fails because of whom" |
| What's the proof? | **Shortest path** from the customer to the cause |
| What would a restart touch? | **Breadth-first search** upstream, plus **betweenness** centrality for risk |
| Have we seen this before? | Overlap of signal patterns between past incidents |

So FalkorDB isn't a cache next to the app; it *is* the app's state. Take it away and nothing groups, ranks, proves,
predicts or remembers.

## How it works

![How RootCause works: the shop's traces flow into one FalkorDB graph; a detector, an engine and a Gemini agent work on it; a person approves the fix](https://raw.githubusercontent.com/rootcause-1/rootcause/main/docs/blog/architecture.png)

1. **The shop.** We used the official [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo): an
   online shop with about twenty services, Kafka, Postgres, a load generator and feature flags that inject real faults.
2. **Collector.** One extra exporter in its OpenTelemetry Collector sends us a copy of every trace.
3. **Ingest, every 5 seconds.** Spans become `(:Service)-[:CALLS {rps, err_rate, p95}]->(:Service)` edges, queues,
   datastores and customer journeys, plus Prometheus metrics, container restarts and feature-flag changes.
4. **FalkorDB.** One graph holds all of it, together with what only a company knows (teams, on-call people,
   runbooks) and the code from GitHub: which folder `IMPLEMENTS` which service, the gRPC APIs it `SERVES`, the
   dependencies it `DECLARES`, and every line where a feature flag is `READ_IN`.
5. **Detector.** Baselines live on the graph's nodes and edges; when a rule fires, the node gets an `:Anomalous`
   label.
6. **Engine.** Groups the alarms, ranks the suspects, finds the proof.
7. **Agent.** A Gemini agent investigates through 16 tools on our MCP server.
8. **Actions.** The safest fix first, and nothing runs without a person.
9. **You.** A live company map and a chat that explains every step.

## Finding the cause, in Cypher

Every 5 seconds we rebuild "blame" edges between anomalous neighbours along the failing calls. A lagging queue blames
its consumer, never its producer:

```cypher
MATCH ()-[b:BLAMES]->() DELETE b;
MATCH (a:Anomalous)-[r:CALLS|USES]->(b:Anomalous)
CREATE (a)-[:BLAMES {weight: coalesce(r.err_rate, 0.0) + 0.01}]->(b);
MATCH (q:Queue:Anomalous)-[:CONSUMED_BY]->(c:Anomalous)
CREATE (q)-[:BLAMES {weight: 1.0}]->(c)
```

Connected components turn an alarm storm into **one incident**:

```cypher
CALL algo.WCC({nodeLabels: ['Anomalous'], relationshipTypes: ['BLAMES']})
YIELD node, componentId
RETURN componentId, collect(node.id) AS members
```

Each suspect then gets a score from five signals:

**score = 0.30·depth + 0.25·own errors + 0.20·PageRank + 0.15·recent change + 0.10·memory**

Depth asks whether the node is at the bottom of the blame chain. PageRank over `BLAMES` shows where the blame flows.
"Recent change" follows `Change -CHANGED-> FeatureFlag -AFFECTS-> Service`, so a flag switched a minute before the
alarms counts. Two general rules handle the tricky cases. If a caller keeps calling a service that has no traffic at
all, the broken thing is the **connection**. A database that didn't change is a **symptom**, not a cause.

The answer comes with proof, the shortest blame path from the customer-facing gateway to the cause:

```cypher
MATCH (a {id: $from}), (b {id: $to})
WITH shortestPath((a)-[:BLAMES*1..8]->(b)) AS p
WHERE p IS NOT NULL
RETURN [n IN nodes(p) | n.id] AS path
```

![The live incident: payment marked as the root cause on the company map; the chat shows the exact line of code and who is hurting](https://raw.githubusercontent.com/rootcause-1/rootcause/main/docs/blog/demo-root-cause.jpg)

Mid-incident, the same story is visible in FalkorDB Browser: only the failing services are left, joined by `BLAMES`
edges.

![FalkorDB Browser mid-incident: four failing services joined by three BLAMES edges](https://raw.githubusercontent.com/rootcause-1/rootcause/main/docs/blog/demo-falkordb-blames.jpg)

One rule we never broke: **the engine never reads the flag configuration to decide a cause.** The flags are only
used afterwards, to score our blind tests.

## An agent that works the graph

The agent connects to our own **MCP server** (16 tools, built with the official Python MCP SDK) and decides which tools
to call: rank the suspects, trace the evidence path, check what changed, measure the customer impact, find who's on
call. Every tool call is a graph query, and every step is saved as a `(:Step)` node that `CITED` the nodes it used.
The reasoning trail becomes part of the graph. The agent may only state facts its tools returned, and it can't run
anything by itself.

## Acting safely

The agent proposes the **safest fix first**. For a bad flag, that's switching it back: low risk. A restart is judged
with the graph too. BFS finds everything upstream, betweenness says how central the service is, and a service that
keeps state is high risk and needs typed confirmation. Approval mints a **single-use token** that expires in
10 minutes. After the fix, RootCause watches every alarm and only marks the incident resolved when all of them have
stayed clear. Then it writes the report and remembers the incident's fingerprint, so next time it can suggest the fix
that worked.

## Fixing it in the code

Switching the flag off stops the bleeding, but the risky code is still there. So RootCause offers a code fix. It
already knows the exact file from the code layer (`READ_IN {file, line}`). It fetches that file from GitHub, Gemini
writes a small change, and RootCause opens a **real pull request** with the graph's evidence in the description. It
never merges anything itself. In our demo run, a person read the diff and merged it.

![The pull request RootCause opened, with the root cause, evidence path, change and customer impact from the graph](https://raw.githubusercontent.com/rootcause-1/rootcause/main/docs/blog/demo-pull-request.jpg)

## Running it on AWS

The live system needs the full OpenTelemetry Demo (about 8 GB of RAM), so for the public site we built a **replay
mode**. We recorded real runs (every trace, metric and change, with timestamps) and play them back through the same
ingest code, into a fresh FalkorDB graph. Visitors see the real incident unfold and can approve the fix themselves;
actions are simulated.

![How RootCause runs on AWS: visitors reach a Graviton EC2 instance running the UI, the API and FalkorDB in Docker Compose; a systemd timer pulls main from GitHub and rebuilds](https://raw.githubusercontent.com/rootcause-1/rootcause/main/docs/blog/aws-deployment.png)

- **Compute:** one **Amazon EC2 t4g.small** (AWS Graviton, ARM, 2 vCPU, 2 GB) on **Amazon Linux 2023**, about
  **$12/month**. FalkorDB, our Python API and the UI all run as ARM containers.
- **Networking:** an **Elastic IP** for a stable address; the security group opens port 80 to everyone and SSH only
  to our own IP.
- **Stack:** **Docker Compose** with three services: FalkorDB `v4.22.1` (pinned, so a new release can't break the
  demo), the RootCause API in replay mode, and the UI on port 80.
- **Deploys:** pull-based. A **systemd timer** on the instance checks `main` every 2 minutes and rebuilds only when it
  moved, so **pushing to GitHub deploys**. There are no deploy keys on the instance and no CI secrets to manage.
- **Safety on a public site:** the public replay has no API keys at all. Gemini and GitHub pull requests only run in
  live mode on our own machine, so anonymous visitors can't spend credits or open PRs.

On a small Graviton instance this is plenty: the replay pushes thousands of spans through the graph every minute with
no trouble.

## Did it work?

We tested it **blind**: a harness switches on one of 16 real faults at random, doesn't tell RootCause, and scores the
answer by code afterwards. In the latest batch of 15, RootCause named the cause first **80%** of the time; blaming the
loudest alarm got **53%**. Gemini given only a flat table of the same alarms also got 80%, but on different runs. It
missed the broken network connection that only the graph could see, and a guess on its own can't prove, judge risk
or fix anything. We publish our misses too. All three were faults where the real cause never raised an alarm.

## What we learned

- **Model the questions first.** Once each on-call question was a graph query, the agent's job became choosing which
  question to ask, which is exactly what tool selection over MCP is good at.
- **Keep the agent honest with the graph.** Citing node ids and saving every step made its answers checkable.
- **Measure against simple baselines.** "Blame the loudest alarm" is a surprisingly strong baseline. Beating it, and
  being honest when an LLM without the graph ties, made the results more useful than one big number.
- **Real systems are messy.** Sparse traffic, partial faults and noisy neighbours taught us more than synthetic data
  could.
- **Small is enough on AWS.** One Graviton instance, Docker Compose and a pull-based timer gave us a public demo that
  redeploys itself.

## Try it

- **Watch:** [the demo, under 5 minutes](https://www.youtube.com/watch?v=tws31rPbplE)
- **Play:** [3.234.90.242](http://3.234.90.242/), then click **Start demo**
- **Read the code:** [github.com/rootcause-1/rootcause](https://github.com/rootcause-1/rootcause) (102 named Cypher
  queries, 207 tests against a real FalkorDB)

*We used Claude Code as an AI coding assistant while building RootCause; the idea, architecture and product decisions
were ours, and the disclosure is in the repo.*
