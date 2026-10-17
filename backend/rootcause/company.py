"""Company setup: the teams, people, ownership, customer journeys and runbooks RootCause reasons with.

They live in the graph (seeded from config/seed.yaml). Every edit here writes the graph, so the next tick already
uses it: who_owns decides who is paged, journeys decide the business impact, runbook automations become proposed
fixes. `to_seed` turns the graph back into seed.yaml so a company can keep its setup in git.

Queries: company_teams, company_journeys, company_runbooks, company_services, company_clear_team,
company_clear_runbook, company_delete, company_reset, seed_org, seed_journeys, seed_runbooks.
"""

from __future__ import annotations

import re
from typing import Any

from rootcause.graph.client import GraphDB
from rootcause.graph.schema import load_seed

RISKS = ("low", "medium", "high")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def team_params(body: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate an edited team -> (team row, people rows) for seed_org. Pure; unit-tested."""
    name = str(body.get("name") or "").strip()
    tid = slug(body.get("id") or "")
    if not tid:
        tid = slug(name)
        if not tid:
            raise ValueError("a team needs a name")
        tid = tid if tid.endswith("-team") else f"{tid}-team"
    owns = sorted({str(s).strip() for s in body.get("owns") or [] if str(s).strip()})
    people = []
    for p in body.get("people") or []:
        pname = str(p.get("name") or "").strip()
        if not pname:
            continue
        people.append({"id": slug(p.get("id") or pname), "name": pname, "on_call": bool(p.get("on_call")),
                       "contact": str(p.get("contact") or ""), "team": tid})
    return {"id": tid, "name": name or tid, "owns": owns}, people


def journey_params(body: dict[str, Any]) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    jid = str(body.get("id") or "").strip() or f"journey:{slug(name).replace('-', '_')}"
    if not name or jid == "journey:":
        raise ValueError("a journey needs a name")
    routes = [str(r).strip() for r in body.get("routes") or [] if str(r).strip()]
    if not routes or any(not r.startswith("/") for r in routes):
        raise ValueError("a journey needs at least one route, each starting with /")
    return {"id": jid, "name": name, "routes": routes}


def runbook_params(body: dict[str, Any]) -> dict[str, Any]:
    service = str(body.get("service") or "").strip()
    title = str(body.get("title") or "").strip()
    if not service or not title:
        raise ValueError("a runbook needs a service and a title")
    url = str(body.get("automation_url") or "").strip()
    if url and not re.match(r"^https?://", url):
        raise ValueError("the automation must be an http(s) URL")
    risk = str(body.get("automation_risk") or "medium")
    if risk not in RISKS:
        raise ValueError(f"automation risk must be one of {', '.join(RISKS)}")
    return {"id": str(body.get("id") or "").strip() or f"rb-{slug(service)}-{slug(title)}"[:60], "service": service,
            "title": title, "url": str(body.get("url") or ""),
            "steps": [str(s).strip() for s in body.get("steps") or [] if str(s).strip()],
            "remediates": [str(s).strip() for s in body.get("remediates") or [] if str(s).strip()],
            "automation_url": url, "automation_risk": risk}


async def get(db: GraphDB, non_candidates: set[str] | frozenset[str]) -> dict[str, Any]:
    teams = await db.run("company_teams")
    for t in teams:
        t["people"] = [p for p in t["people"] if p.get("id")]
    return {
        "teams": teams,
        "journeys": await db.run("company_journeys"),
        "runbooks": await db.run("company_runbooks"),
        "services": [r["id"] for r in await db.run("company_services") if r["id"] not in non_candidates],
    }


async def journeys(db: GraphDB) -> list[dict[str, Any]]:
    """Journey routes for span ingestion, read back from the graph after an edit."""
    return [{"id": j["id"], "routes": j["routes"] or []} for j in await db.run("company_journeys")]


async def save_team(db: GraphDB, body: dict[str, Any]) -> dict[str, Any]:
    team, people = team_params(body)
    await db.run("company_clear_team", id=team["id"])
    await db.run("seed_org", teams=[team], people=people)
    return team | {"people": people}


async def save_journey(db: GraphDB, body: dict[str, Any]) -> dict[str, Any]:
    j = journey_params(body)
    await db.run("seed_journeys", journeys=[j])
    return j


async def save_runbook(db: GraphDB, body: dict[str, Any]) -> dict[str, Any]:
    rb = runbook_params(body)
    await db.run("company_clear_runbook", id=rb["id"])
    await db.run("seed_runbooks", runbooks=[rb])
    return rb


async def delete(db: GraphDB, node_id: str) -> None:
    await db.run("company_delete", id=node_id)


async def reset(db: GraphDB, seed: dict[str, Any]) -> None:
    """Back to config/seed.yaml."""
    await db.run("company_reset", keep=[j["id"] for j in seed.get("journeys", [])])
    await load_seed(db, seed)


def to_seed(company: dict[str, Any]) -> dict[str, Any]:
    """The graph's company setup in seed.yaml shape (flag_service_map is not part of the setup). Pure."""
    return {
        "teams": [{"id": t["id"], "name": t["name"],
                   "people": [{k: p[k] for k in ("id", "name", "on_call", "contact") if p.get(k) is not None}
                              for p in t["people"]],
                   "owns": sorted(t["owns"])} for t in company["teams"]],
        "journeys": [{"id": j["id"], "name": j["name"], "routes": j["routes"] or []} for j in company["journeys"]],
        "runbooks": [{k: v for k, v in {
            "id": r["id"], "service": r["service"], "title": r["title"], "url": r.get("url") or None,
            "steps": r.get("steps") or [], "remediates": r.get("remediates") or [],
            "automation_url": r.get("automation_url") or None,
            "automation_risk": r.get("automation_risk") if r.get("automation_url") else None}.items()
            if v is not None} for r in company["runbooks"]],
    }
