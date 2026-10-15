"""Run one live acceptance check against the running stack (CLAUDE.md §12, M3-M6) and print the evidence.

Flips a flag in the demo's flagd JSON (as a human would), then prints a timeline: when the Change node appeared,
when each alert fired, the incident's ranked hypotheses, evidence path, change, impact and proposals.
With --approve it approves the top proposal through the API (as the UI does) and waits for the incident to be
resolved and the report written. Without --approve it reverts the flag itself at the end.

Usage: uv run python scripts/acceptance_check.py --flag paymentFailure [--variant 100%] [--approve] [--wait 150]
Needs FalkorDB on localhost:6380 (make up) and the API on localhost:8000. Read-only graph access.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
from falkordb import FalkorDB

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from rootcause.actions.flagd import set_variant  # noqa: E402
from rootcause.chaos.runner import load_catalogue  # noqa: E402

FLAGD = Path(__file__).resolve().parents[2] / "opentelemetry-demo" / "src" / "flagd" / "demo.flagd.json"


def rows(g, q: str) -> list[list]:
    return g.ro_query(q).result_set


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flag", required=True)
    ap.add_argument("--variant")
    ap.add_argument("--wait", type=int, default=150, help="seconds to watch after the flip")
    ap.add_argument("--approve", action="store_true", help="approve the top proposal and wait for resolution")
    ap.add_argument("--settle", type=int, default=60, help="seconds to keep watching after the first verdict")
    ap.add_argument("--flagd", default=str(FLAGD))
    ap.add_argument("--graph", default="rc_live")
    args = ap.parse_args()
    entry = next((e for e in load_catalogue() if e["flag"] == args.flag), {})
    variant = args.variant or entry.get("variant", "on")
    g = FalkorDB(host="localhost", port=6380).select_graph(args.graph)
    api = httpx.Client(base_url="http://localhost:8000", timeout=60)

    before = {r[0] for r in rows(g, "MATCH (i:Incident) RETURN i.id")}
    t0 = int(time.time() * 1000)
    set_variant(args.flagd, args.flag, variant, actor="harness")
    print(f"t=0s  flag {args.flag} -> {variant}")
    seen_alerts: set[str] = set()
    change_seen = False
    inc_id = None
    verdict_at = None
    deadline = time.time() + args.wait
    while time.time() < deadline:
        if not change_seen:
            ch = rows(g, f"MATCH (c:Change)-[:CHANGED]->(f:FeatureFlag {{id:'{args.flag}'}}) WHERE c.ts >= {t0 - 1000} "
                         "RETURN c.id, c.ts, c.from_variant, c.to")
            if ch:
                change_seen = True
                print(f"t={(ch[0][1] - t0) / 1000:.1f}s  Change {ch[0][0]}: {ch[0][2]} -> {ch[0][3]}")
        for aid, target, kind, ts, value in rows(g, f"MATCH (a:Alert) WHERE a.ts >= {t0} RETURN a.id, a.target, "
                                                    "a.kind, a.ts, a.value ORDER BY a.ts"):
            if aid not in seen_alerts:
                seen_alerts.add(aid)
                print(f"t={(ts - t0) / 1000:.1f}s  ALERT {kind} on {target} (value {value:.3g})")
        new = [r for r in rows(g, "MATCH (i:Incident) WHERE i.status = 'open' RETURN i.id, i.agent_state, "
                                  "i.verdict_root ORDER BY i.created_ts") if r[0] not in before]
        if new and inc_id is None:
            inc_id = new[0][0]
            print(f"t={(time.time() * 1000 - t0) / 1000:.1f}s  incident {inc_id} opened")
        if inc_id and any(r[0] == inc_id and r[1] in ("awaiting_approval", "done") for r in new):
            verdict_at = verdict_at or time.time()
            if time.time() - verdict_at >= args.settle:  # a human reads the verdict before approving
                break
        time.sleep(2)

    open_ids = [r[0] for r in rows(g, "MATCH (i:Incident) WHERE i.status='open' RETURN i.id") if r[0] not in before]
    print(f"\nopen incidents created by this flip: {open_ids}")
    for iid in open_ids:
        inc = api.get(f"/api/incidents/{iid}").json()
        v = json.loads(inc["verdict"]) if isinstance(inc.get("verdict"), str) else (inc.get("verdict") or {})
        print(f"\n== {iid}  members={inc.get('members')}  alerts={inc.get('alert_count', len(inc.get('alerts', [])))}")
        for h in (inc.get("hypotheses") or [])[:3]:
            sig = {k: h.get(k) for k in ("depth", "self", "pagerank", "change", "memory")}
            print(f"   #{h.get('rank')} {h.get('target')}  score={h.get('score')}  {sig}")
        print(f"   evidence path: {inc.get('evidence_path')}")
        print(f"   change: {v.get('change')}")
        print(f"   impact: {[(i.get('journey'), i.get('pct')) for i in (v.get('impact') or []) if i.get('impacted')]}")
        print(f"   proposals: {[(a['kind'], a['target'], a['risk']) for a in v.get('proposed_actions', [])]}")
        print(f"   verdict: root={v.get('root_cause')} confidence={v.get('confidence')} "
              f"verdict at t={(int(v.get('verdict_ts', t0)) - t0) / 1000:.1f}s")

    if args.approve and open_ids:
        inc = api.get(f"/api/incidents/{open_ids[0]}").json()
        v = json.loads(inc["verdict"]) if isinstance(inc.get("verdict"), str) else inc["verdict"]
        act = v["proposed_actions"][0]
        print(f"\napproving {act['id']} ({act['kind']} {act['target']}, risk {act['risk']})")
        print("  ", json.dumps(api.post(f"/api/actions/{act['id']}/approve", json={}).json())[:300])
        t1 = time.time()
        while time.time() - t1 < 180:
            st = rows(g, f"MATCH (i:Incident {{id:'{open_ids[0]}'}}) OPTIONAL MATCH (i)-[:HAS_REPORT]->(r:Report) "
                         "RETURN i.status, i.ttr_ms, i.resolution, r.path")
            if st and st[0][0] == "resolved":
                print(f"   resolved after {time.time() - t1:.0f}s: ttr_ms={st[0][1]} resolution={st[0][2]} "
                      f"report={st[0][3]}")
                break
            time.sleep(3)
        else:
            print("   NOT resolved within 180 s")
    else:
        set_variant(args.flagd, args.flag, entry.get("off", "off"), actor="harness")
        print(f"\nreverted {args.flag} (harness)")


if __name__ == "__main__":
    main()
