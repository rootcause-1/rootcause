"""Schema bootstrap (indexes) and seed loader for config/seed.yaml.

Queries used: seed_org, seed_journeys, seed_runbooks, seed_flags.
The CREATE INDEX statements are the only inline Cypher in the codebase (allowed: trivial schema bootstrapping).

Run `python -m rootcause.graph.schema --seed` (what `make seed` does).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from rootcause.graph.client import GraphDB, get_graph
from rootcause.settings import get_settings

log = logging.getLogger(__name__)

LABELS = [
    "Service", "Queue", "Datastore", "Container", "Journey", "Team", "Person", "Runbook", "FeatureFlag",
    "Change", "Alert", "Incident", "SignalPattern", "Hypothesis", "Action", "Prediction", "Step", "Report",
    "ChaosRun",
]


async def ensure_indexes(db: GraphDB) -> None:
    for label in LABELS:
        try:
            await db.raw(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
        except Exception as exc:  # "already indexed" is fine
            if "already" not in str(exc).lower():
                raise
    # status filters are hot in the detector and engine
    for label in ("Alert", "Incident", "Action"):
        try:
            await db.raw(f"CREATE INDEX FOR (n:{label}) ON (n.status)")
        except Exception as exc:
            if "already" not in str(exc).lower():
                raise


def seed_params(seed: dict[str, Any]) -> dict[str, Any]:
    """Turn seed.yaml into the parameter lists of the seed_* queries (pure function, unit-tested)."""
    teams = [{"id": t["id"], "name": t.get("name", t["id"]), "owns": t.get("owns", [])} for t in seed.get("teams", [])]
    people = [
        {"id": p["id"], "name": p.get("name", p["id"]), "on_call": bool(p.get("on_call", False)),
         "contact": p.get("contact", ""), "team": t["id"]}
        for t in seed.get("teams", []) for p in t.get("people", [])
    ]
    journeys = [{"id": j["id"], "name": j.get("name", j["id"]), "routes": j.get("routes", [])}
                for j in seed.get("journeys", [])]
    runbooks = [
        {"id": r["id"], "service": r["service"], "title": r.get("title", ""), "url": r.get("url", ""),
         "steps": r.get("steps", []), "remediates": r.get("remediates", []),
         "automation_url": r.get("automation_url", ""), "automation_risk": r.get("automation_risk", "medium")}
        for r in seed.get("runbooks", [])
    ]
    flags = [{"id": k, "services": v} for k, v in (seed.get("flag_service_map") or {}).items()]
    return {"teams": teams, "people": people, "journeys": journeys, "runbooks": runbooks, "flags": flags}


async def load_seed(db: GraphDB, seed: dict[str, Any] | None = None) -> dict[str, int]:
    p = seed_params(seed if seed is not None else get_settings().seed)
    await db.run("seed_org", teams=p["teams"], people=p["people"])
    await db.run("seed_journeys", journeys=p["journeys"])
    await db.run("seed_runbooks", runbooks=p["runbooks"])
    await db.run("seed_flags", flags=p["flags"])
    return {k: len(v) for k, v in p.items()}


async def _main(seed: bool) -> None:
    db = get_graph()
    await ensure_indexes(db)
    if seed:
        counts = await load_seed(db)
        print(f"seeded {db.name}: {counts}")
    rows = await db.raw("MATCH (n) RETURN labels(n) AS labels, count(*) AS n", read_only=True)
    for r in rows:
        print(r["labels"], r["n"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    asyncio.run(_main(ap.parse_args().seed))
