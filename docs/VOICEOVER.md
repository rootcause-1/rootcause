# RootCause demo video (v3, 4:12) — voice-over script

Mute the video's audio and start each block at its time stamp. The text is exactly what the draft voice says;
you can speak a little faster than the draft voice. Pronunciations: FalkorDB = "Falkor D B", MCP = "M C P".

## 0:00–0:19 · The problem

Picture an online shop. Behind the website, dozens of small services call each other. Now payment breaks. Checkout fails too, because it needs payment. Then the storefront, then the gateway. Two teams get paged at 3 AM. Four alarms, and every one is real. But only one service is actually broken. Finding it by hand is the slowest part of every outage.

## 0:19–0:27 · Title

This is RootCause: an AI on-call engineer that sees your system as a graph, finds the one real cause, and fixes it with your OK.

## 0:27–0:56 · How it works

Here's how it works. The OpenTelemetry Demo shop, through its collector, sends every trace to RootCause. Every five seconds, traces, metrics and changes become calls, queues and customer journeys, all in one FalkorDB graph, together with the code from GitHub. A detector learns normal and raises alarms. The engine walks the graph to group them and rank the suspects. A Gemini agent investigates through our MCP tools, and proposes the safest fix for you to approve. Then it checks the fix worked, and opens the code fix as a pull request.

## 0:56–1:02 · The real shop

Let's see it live. This is the demo shop on our laptop, with real shoppers generated all the time.

## 1:02–1:18 · The graph builds itself

We start RootCause with an empty graph. Watch the map: it's being built right now, in real time, from that traffic. Five seconds in, thirteen services, each in its team's lane. A few seconds later, all nineteen, with the customers on the left, and it starts learning what normal looks like.

## 1:18–1:30 · Connect GitHub

Next, we connect the shop's GitHub repo. The code goes into the same graph: which folder runs as which service, its APIs, and every line that reads a feature flag. It even flags where the code and the live traffic disagree.

## 1:30–1:38 · The code layer in FalkorDB

Inside FalkorDB, the code layer now sits right on top of the live service graph, with every module linked to the service it runs as.

## 1:38–1:50 · The API map

It maps the APIs too: every gRPC service in the code, and the module that serves it, every dependency the modules declare, and where live traffic disagrees: here, a production call the code never declares.

## 1:50–2:01 · Break it

Now we break it the way real outages start: someone changes a setting. Payment failure goes to one hundred percent, A customer tries to pay, and the shop's API rejects it. Nobody tells RootCause.

## 2:01–2:12 · Alarms become one incident

Watch the steps at the top. Alarms fire on the storefront, the gateway, checkout and payment. RootCause sees they're connected in the graph, so it opens one incident instead of paging two teams.

## 2:12–2:19 · BLAMES in FalkorDB

In FalkorDB, only the failing services are left, joined by the calls that fail. Connected components make them one incident.

## 2:19–2:33 · Gemini investigates

Now the Gemini agent investigates. It decides which tools to call on our MCP server, and every call is a query on the FalkorDB graph: rank the suspects, trace the evidence path, check what changed, measure the customer impact, and find who's on call.

## 2:33–2:45 · Root cause

Found it: payment. The blame trail runs from the gateway down to payment and stops, because payment's own requests are failing, and its flag changed just before the first alarm. It even points to the exact line of code.

## 2:45–2:53 · The fix, approved

It proposes the safest fix: switch the flag back. Low risk. A restart would be high risk, because the graph shows what depends on payment. I approve.

## 2:53–3:02 · Verified recovery

RootCause applies it, waits until every alarm has cleared, and only then marks it resolved and writes the report. Here, all four alarms cleared in eighty-five seconds.

## 3:02–3:13 · Fix it in code

The failing code is still there, so RootCause offers a code fix. I say yes. It reads the exact file from GitHub, Gemini writes a small change, and RootCause opens a pull request on our fork.

## 3:13–3:23 · The pull request

Here's that pull request on GitHub: Gemini's explanation, plus the evidence from the graph: root cause, blame path, change and impact. And the change itself, in the payment code.

## 3:23–3:29 · A person merges

A person reviews the change and merges it. RootCause never merges anything by itself.

## 3:29–3:38 · One graph

And it's all one graph in FalkorDB: the alerts and their incident, every step the agent took, and what it cited, and the pull request, linked to the root cause and the code it changed.

## 3:38–3:53 · More features

There's more. Predict walks the graph upstream to show what would break, before it breaks. Memory keeps every incident and the fix that worked, to suggest it first next time. Reports are written straight from the graph. And Your company sets up teams, on-call and runbooks, all in FalkorDB.

## 3:53–4:02 · Proof

We tested it blind: fifteen random faults, scored by code. RootCause named the cause first eighty percent of the time. Blaming the loudest alarm got fifty-three.

## 4:02–4:12 · Close

Behind it: a hundred and two Cypher queries, two hundred and seven tests on a real FalkorDB, and a public demo you can try. RootCause: one cause, one fix, one pull request.

_794 words in total._
