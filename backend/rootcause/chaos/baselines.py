"""Baseline root-cause methods the scorecard compares RootCause against, all on the same alert snapshot:

- loudest_alert: node with the most alerts
- first_alert:   node of the earliest alert
- highest_error: node with the highest error rate
- graph_off:     our own ranking with depth, pagerank, change and memory disabled (self signal only)
- llm_no_graph:  the same LLM given only a flat table of alerts and per-service metrics, no tools (needs API key)

Queries: incident_alert_snapshot, graph_nodes (+ hypotheses via facts.py).
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

from rootcause.engine import ranking
from rootcause.graph.client import GraphDB
from rootcause.settings import Settings

log = logging.getLogger(__name__)


def loudest_alert(alerts: list[dict[str, Any]]) -> list[str]:
    counts = Counter(a["target"] for a in alerts)
    first = {}
    for a in sorted(alerts, key=lambda a: a["ts"]):
        first.setdefault(a["target"], a["ts"])
    return sorted(counts, key=lambda t: (-counts[t], first[t], t))


def first_alert(alerts: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for a in sorted(alerts, key=lambda a: (a["ts"], a["target"])):
        if a["target"] not in out:
            out.append(a["target"])
    return out


def highest_error(alerts: list[dict[str, Any]]) -> list[str]:
    best: dict[str, float] = {}
    for a in alerts:
        best[a["target"]] = max(best.get(a["target"], 0.0), float(a.get("err_rate") or 0.0))
    return sorted(best, key=lambda t: (-best[t], t))


def graph_off(hypotheses: list[dict[str, Any]], weights: dict[str, float]) -> list[str]:
    cands = [ranking.Candidate(target=h["target"], node=h["target"], **{s: float(h.get(s) or 0.0)
                                                                           for s in ranking.SIGNALS})
             for h in hypotheses]
    return [c.target for c in ranking.rank(cands, weights, disabled={"depth", "pagerank", "change", "memory"})]


async def llm_no_graph(s: Settings, alerts: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[str] | None:
    if not s.anthropic_api_key:
        return None
    from rootcause.agent.loop import _client, _create, parse_verdict

    table = {"alerts": [{k: a.get(k) for k in ("target", "kind", "ts", "value")} for a in alerts],
             "services": [{k: n.get(k) for k in ("id", "rps", "err_rate", "p95_ms", "cpu_pct", "mem_mb")}
                          for n in nodes]}
    prompt = ("These alerts fired together in a microservice shop. Which single node is the root cause? "
              "Reply only with JSON: {\"ranked\": [\"<node id>\", \"<2nd>\", \"<3rd>\"]}\n" + json.dumps(table))
    try:
        resp = await _create(_client(s), s, messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if b.type == "text")
        out = parse_verdict(text) or {}
        return [str(x) for x in out.get("ranked", [])]
    except Exception as exc:
        log.warning("llm_no_graph baseline failed: %s", exc)
        return None


async def run_all(db: GraphDB, s: Settings, incident_id: str, hypotheses: list[dict[str, Any]]
                  ) -> dict[str, list[str] | None]:
    alerts = await db.run("incident_alert_snapshot", id=incident_id)
    nodes = await db.run("graph_nodes")
    return {
        "loudest_alert": loudest_alert(alerts),
        "first_alert": first_alert(alerts),
        "highest_error": highest_error(alerts),
        "graph_off": graph_off(hypotheses, s.c("engine", "weights")),
        "llm_no_graph": await llm_no_graph(s, alerts, nodes),
    }
