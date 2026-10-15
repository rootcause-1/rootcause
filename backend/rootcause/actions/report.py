"""Post-incident report: facts gathered with queries, narrated by the LLM if enabled, else a template.

Queries: get_incident / get_steps / incident_actions (via facts.py), evidence (engine/evidence.py),
similar_incidents (engine/memory.py), create_report. Saves (:Report) + reports/INC-xxxx.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rootcause import facts
from rootcause.engine import evidence, memory
from rootcause.graph.client import GraphDB
from rootcause.settings import get_settings
from rootcause.util import now_ms

log = logging.getLogger(__name__)


def _t(ms: int | None) -> str:
    if not ms:
        return "-"
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%H:%M:%S UTC")


def render(inc: dict[str, Any], path: list[str], similar: list[dict[str, Any]], narrative: str | None,
           verdict: dict[str, Any] | None = None) -> str:
    """`verdict` is the agent's snapshot at diagnosis time; it wins over the (already recovered) live graph."""
    verdict = verdict or {}
    root = verdict.get("root_cause") or inc.get("root_target") or "unknown"
    path = verdict.get("evidence_path") or path
    impact = [i for i in (verdict.get("impact") or inc["impact"]) if i.get("impacted", True) and i.get("pct")]
    lines = [f"# {inc['id']} — root cause: `{root}`", ""]
    lines += [f"- **Status:** {inc.get('status')} ({inc.get('resolution') or 'open'})",
              f"- **Opened:** {_t(inc.get('created_ts'))}  **Resolved:** {_t(inc.get('resolved_ts'))}",
              f"- **Time to resolve:** {round((inc.get('ttr_ms') or 0) / 1000)} s",
              f"- **Confidence:** {verdict.get('confidence') or inc.get('confidence') or 0:.2f}",
              f"- **Alerts grouped:** {len(inc['alerts'])} alerts → 1 incident", ""]
    if narrative:
        lines += ["## Summary", "", narrative, ""]
    lines += ["## Evidence path", "", " → ".join(f"`{p}`" for p in path) or "-", ""]
    lines += ["## Ranked hypotheses", "", "| # | target | score | depth | self | pagerank | change | memory |",
              "|---|---|---|---|---|---|---|---|"]
    for h in inc["hypotheses"][:5]:
        lines.append(f"| {h['rank']} | `{h['target']}` | {h['score']:.2f} | {h['depth']:.2f} | {h['self']:.2f} | "
                     f"{h['pagerank']:.2f} | {h['change']:.2f} | {h['memory']:.2f} |")
    lines += ["", "## What changed", ""]
    lines += [f"- {_t(c['ts'])} `{c['target']}` {c.get('from_variant') or ''} → {c.get('to') or c['kind']} "
              f"(actor: {c.get('actor')})" for c in inc["changes"]] or ["- no change found near onset"]
    lines += ["", "## User impact", ""]
    lines += [f"- {i['journey']}: {i['pct']:.0%} drop in success" for i in impact] or ["- none measured"]
    lines += ["", "## Timeline", ""]
    events = [(a["ts"], f"alert `{a['kind']}` on `{a['target']}`") for a in inc["alerts"]]
    events += [(s["ts"], f"agent step {s['n']}: `{s['tool']}` — {s['summary']}") for s in inc["steps"]]
    events += [(a.get("executed_ts") or a.get("ts"), f"action `{a['kind']}` on `{a['target']}`: {a['status']}")
               for a in inc["actions"] if a["status"] != "proposed"]
    lines += [f"- {_t(ts)} {what}" for ts, what in sorted(events, key=lambda e: e[0] or 0)]
    lines += ["", "## Similar past incidents", ""]
    lines += [f"- {s['incident']} (similarity {s['score']:.2f}, root `{s.get('root')}`, fixed by "
              f"{', '.join(s['fixes']) or '-'})" for s in similar] or ["- none"]
    return "\n".join(lines) + "\n"


async def write(db: GraphDB, incident_id: str, narrator: Any = None) -> dict[str, Any]:
    s = get_settings()
    inc = await facts.full(db, incident_id)
    if inc is None:
        return {"error": f"no incident {incident_id}"}
    root = inc.get("root_target") or ""
    path = await evidence.path(db, inc.get("members") or [], root) if root else []
    similar = await memory.similar(db, incident_id, root)
    narrative = None
    if narrator is not None:
        try:
            narrative = await narrator(inc, path, similar)
        except Exception as exc:
            log.warning("LLM narration failed, using template only: %s", exc)
    md = render(inc, path, similar, narrative, inc.get("verdict") if isinstance(inc.get("verdict"), dict) else None)
    out_dir = Path(s.rc_reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    file = out_dir / f"{incident_id}.md"
    file.write_text(md, encoding="utf-8")
    await db.run("create_report", id=f"RPT-{incident_id}", incident=incident_id, markdown=md, now=now_ms(),
                 path=str(file.name))
    return {"report_id": f"RPT-{incident_id}", "path": f"reports/{file.name}", "markdown": md,
            "evidence": [incident_id, *path]}
