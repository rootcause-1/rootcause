"""Narration for the demo video, one entry per segment, one string per sentence (each sentence is voiced separately
so beats can land on sentence starts). `say` = what is shown in subtitles; TTS gets `speak()` with pronunciations."""

SEGMENTS = [
    ("intro", [
        "Picture an online shop.",
        "Behind the website, dozens of small services call each other.",
        "Now payment breaks.",
        "Checkout fails too, because it needs payment. Then the storefront, then the gateway.",
        "Two teams get paged at 3 AM.",
        "Four alarms, and every one is real.",
        "But only one service is actually broken.",
        "Finding it by hand is the slowest part of every outage.",
    ]),
    ("title", [
        "This is RootCause: an AI on-call engineer that sees your system as a graph, finds the one real cause, and fixes it with your OK.",
    ]),
    ("pipeline", [
        "Here's how it works. The OpenTelemetry Demo shop, through its collector, sends every trace to RootCause.",
        "Every five seconds, traces, metrics and changes become calls, queues and customer journeys,",
        "all in one FalkorDB graph,",
        "together with the code from GitHub.",
        "A detector learns normal and raises alarms.",
        "The engine walks the graph to group them and rank the suspects.",
        "A Gemini agent investigates through our MCP tools,",
        "and proposes the safest fix for you to approve.",
        "Then it checks the fix worked, and opens the code fix as a pull request.",
    ]),
    ("shop", [
        "Let's see it live. This is the demo shop on our laptop, with real shoppers generated all the time.",
    ]),
    ("build", [
        "We start RootCause with an empty graph.",
        "Watch the map: it's being built right now, in real time, from that traffic.",
        "Five seconds in, thirteen services, each in its team's lane.",
        "A few seconds later, all nineteen, with the customers on the left,",
        "and it starts learning what normal looks like.",
    ]),
    ("github", [
        "Next, we connect the shop's GitHub repo.",
        "The code goes into the same graph: which folder runs as which service, its APIs, and every line that reads a feature flag.",
        "It even flags where the code and the live traffic disagree.",
    ]),
    ("layers", [
        "Inside FalkorDB, the code layer now sits right on top of the live service graph,",
        "with every module linked to the service it runs as.",
    ]),
    ("apis", [
        "It maps the APIs too: every gRPC service in the code, and the module that serves it,",
        "every dependency the modules declare,",
        "and where live traffic disagrees: here, a production call the code never declares.",
    ]),
    ("break", [
        "Now we break it the way real outages start: someone changes a setting.",
        "Payment failure goes to one hundred percent,",
        "A customer tries to pay, and the shop's API rejects it. Nobody tells RootCause.",
    ]),
    ("alarms", [
        "Watch the steps at the top.",
        "Alarms fire on the storefront, the gateway, checkout and payment.",
        "RootCause sees they're connected in the graph, so it opens one incident instead of paging two teams.",
    ]),
    ("blames", [
        "In FalkorDB, only the failing services are left, joined by the calls that fail. Connected components make them one incident.",
    ]),
    ("investigate", [
        "Now the Gemini agent investigates.",
        "It decides which tools to call on our MCP server, and every call is a query on the FalkorDB graph:",
        "rank the suspects, trace the evidence path, check what changed, measure the customer impact, and find who's on call.",
    ]),
    ("root", [
        "Found it: payment.",
        "The blame trail runs from the gateway down to payment and stops, because payment's own requests are failing, and its flag changed just before the first alarm.",
        "It even points to the exact line of code.",
    ]),
    ("fix", [
        "It proposes the safest fix: switch the flag back. Low risk.",
        "A restart would be high risk, because the graph shows what depends on payment.",
        "I approve.",
    ]),
    ("recover", [
        "RootCause applies it, waits until every alarm has cleared, and only then marks it resolved and writes the report.",
        "Here, all four alarms cleared in eighty-five seconds.",
    ]),
    ("pr", [
        "The failing code is still there, so RootCause offers a code fix.",
        "I say yes.",
        "It reads the exact file from GitHub, Gemini writes a small change, and RootCause opens a pull request on our fork.",
    ]),
    ("github_pr", [
        "Here's that pull request on GitHub: Gemini's explanation, plus the evidence from the graph: root cause, blame path, change and impact.",
        "And the change itself, in the payment code.",
    ]),
    ("merge", [
        "A person reviews the change and merges it. RootCause never merges anything by itself.",
    ]),
    ("onegraph", [
        "And it's all one graph in FalkorDB: the alerts and their incident,",
        "every step the agent took, and what it cited,",
        "and the pull request, linked to the root cause and the code it changed.",
    ]),
    ("tabs", [
        "There's more. Predict walks the graph upstream to show what would break, before it breaks.",
        "Memory keeps every incident and the fix that worked, to suggest it first next time.",
        "Reports are written straight from the graph.",
        "And Your company sets up teams, on-call and runbooks, all in FalkorDB.",
    ]),
    ("score", [
        "We tested it blind: fifteen random faults, scored by code.",
        "RootCause named the cause first eighty percent of the time. Blaming the loudest alarm got fifty-three.",
    ]),
    ("end", [
        "Behind it: a hundred and two Cypher queries, two hundred and seven tests on a real FalkorDB, and a public demo you can try.",
        "RootCause: one cause, one fix, one pull request.",
    ]),
]

SAY = {"FalkorDB": "Falkor D B", "MCP": "M C P", "3 AM": "three A M", "OpenTelemetry": "Open Telemetry",
       "RootCause": "Root Cause", "GitHub": "Git Hub", "on-call": "on call", "PageRank": "Page Rank"}


def speak(s):
    for k, v in SAY.items():
        s = s.replace(k, v)
    return s
