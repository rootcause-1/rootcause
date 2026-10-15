"""Action lifecycle: propose -> approve (mints a single-use token, 10 min TTL) -> execute -> verify -> report.

Proposals for an incident's top hypothesis:
1. fixes of a strong memory match (similarity >= 0.6) first,
2. revert each flag change linked to the incident (CAUSED_BY) — risk low,
3. restart the root service's container — risk from betweenness/statefulness,
4. page the owning team — risk none, always last (it informs, it does not fix).
Fixing actions are ordered by risk, then expected effectiveness (revert > restart).

Queries: create_action, clear_proposed_actions, get_action, set_action_props, set_incident_props, who_owns
(+ the queries behind facts.py, safety.py, memory.py). In replay mode actions are simulated: logged, not executed,
and the replay player is told so it can jump to the recording's recovery segment.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from rootcause import facts
from rootcause.actions import containers, flagd, pager, report, verify
from rootcause.engine import memory, safety
from rootcause.graph.client import GraphDB
from rootcause.settings import Settings
from rootcause.util import dumps, new_id, now_ms

log = logging.getLogger(__name__)
TOKEN_TTL_MS = 10 * 60 * 1000
EFFECTIVENESS = {"flag_revert": 0, "restart": 1, "page": 2}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def order(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Memory-backed fixes first, then by risk, then effectiveness; paging always last. Pure; unit-tested."""
    return sorted(proposals, key=lambda p: (
        p["kind"] == "page", not p.get("from_memory"), safety.RISK_ORDER[p["risk"]], EFFECTIVENESS[p["kind"]]))


def confirm_phrase(action: dict[str, Any]) -> str | None:
    return f"RESTART {action['target']}" if action.get("risk") == "high" else None


class ActionService:
    def __init__(self, db: GraphDB, settings: Settings, publish: Callable[[str, Any], Awaitable[None]] | None = None,
                 on_simulated: Callable[[dict[str, Any]], Awaitable[None]] | None = None, narrator: Any = None):
        self.db = db
        self.s = settings
        self.publish = publish
        self.on_simulated = on_simulated  # replay player hook
        self.narrator = narrator
        self.tasks: set[asyncio.Task[Any]] = set()

    @property
    def simulated(self) -> bool:
        return self.s.rc_mode == "replay"

    async def _emit(self, event: str, data: Any) -> None:
        if self.publish:
            await self.publish(event, data)

    # ---------------------------------------------------------------- propose
    async def propose(self, incident_id: str) -> dict[str, Any]:
        db = self.db
        inc = await facts.full(db, incident_id)
        if inc is None:
            return {"error": f"no incident {incident_id}"}
        root = inc.get("root_target")
        if not root:
            return {"incident": incident_id, "actions": [], "evidence": [incident_id],
                    "note": "no root cause ranked yet"}
        failed = {(a["kind"], a["target"]) for a in inc["actions"] if a["status"] == "failed"}
        root_service = root.split("->", 1)[1] if root.startswith("edge:") else root
        strong = float(self.s.c("engine", "strong_memory", default=0.6))

        proposals: list[dict[str, Any]] = []
        for sim in await memory.similar(db, incident_id, root):
            if sim["score"] < strong:
                continue
            for fix in sim["fixes"]:
                kind, _, target = fix.partition(":")
                if kind == "restart":
                    proposals.append({"kind": "restart", "target": target, "params": {}, "from_memory": sim["incident"],
                                      "reason": f"restart of {target} fixed similar {sim['incident']} "
                                                f"(similarity {sim['score']:.2f})"})
        for ch in inc["changes"]:
            if ch["kind"] == "flag" and ch.get("from_variant") is not None:
                proposals.append({"kind": "flag_revert", "target": ch["target"],
                                  "params": {"variant": ch["from_variant"], "change": ch["id"]},
                                  "reason": f"{ch['target']} changed {ch['from_variant']} → {ch['to']} right before "
                                            f"onset and affects {root}"})
        if not root_service.startswith(("queue:", "db:", "cache:")):
            proposals.append({"kind": "restart", "target": root_service, "params": {},
                              "reason": f"{root_service} is the ranked root cause"})
        owner = await db.run("who_owns", node_id=root_service)
        team = owner[0]["team"] if owner else None
        proposals.append({"kind": "page", "target": team or "platform-team", "params": {"incident": incident_id},
                          "reason": f"{team or 'platform-team'} owns {root_service}"})

        seen: set[tuple[str, str]] = set()
        unique = []
        for p in proposals:
            key = (p["kind"], p["target"])
            if key in seen or key in failed:
                continue
            seen.add(key)
            unique.append(p)

        stateful = list(self.s.c("safety", "stateful_datastores", default=[]))
        high_pct = float(self.s.c("safety", "high_betweenness_percentile", default=0.8))
        for p in unique:
            if p["kind"] == "flag_revert":
                p["safety"] = await safety.assess_flag(db, p["target"])
            elif p["kind"] == "restart":
                p["safety"] = await safety.assess_restart(db, p["target"], stateful, high_pct)
            else:
                p["safety"] = safety.assess_page(p["target"])
            p["risk"] = p["safety"]["risk"]

        await db.run("clear_proposed_actions", id=incident_id)
        out = []
        for i, p in enumerate(order(unique), start=1):
            aid = new_id("ACT")
            await db.run("create_action", id=aid, incident=incident_id, kind=p["kind"], target=p["target"],
                         params=dumps(p["params"]), risk=p["risk"], side_effects=dumps(p["safety"]),
                         reason=p["reason"], rank=i, now=now_ms())
            out.append({"id": aid, "kind": p["kind"], "target": p["target"], "risk": p["risk"], "rank": i,
                        "reason": p["reason"], "side_effects": p["safety"], "params": p["params"],
                        "confirm": confirm_phrase(p)})
        await db.run("set_incident_props", id=incident_id, props={"agent_state": "awaiting_approval"})
        await self._emit("action", {"incident": incident_id, "proposed": out})
        return {"incident": incident_id, "actions": out,
                "evidence": [incident_id, root_service, *[p["target"] for p in out]]}

    # ---------------------------------------------------------------- approve / reject
    async def approve(self, action_id: str, confirm: str | None = None) -> dict[str, Any]:
        a = await self._get(action_id)
        if a is None:
            return {"error": f"no action {action_id}"}
        if a["status"] != "proposed":
            return {"error": f"action {action_id} is {a['status']}"}
        phrase = confirm_phrase(a)
        if phrase and (confirm or "").strip() != phrase:
            return {"error": f"high-risk action: type exactly '{phrase}' to confirm", "confirm": phrase}
        token = secrets.token_urlsafe(18)
        await self.db.run("set_action_props", id=action_id, props={
            "status": "approved", "approval_hash": _hash(token), "approval_expires": now_ms() + TOKEN_TTL_MS,
            "approval_used": False, "approved_ts": now_ms()})
        await self._emit("action", {"id": action_id, "status": "approved"})
        return {"action": action_id, "approval_token": token, "expires_in_s": TOKEN_TTL_MS // 1000}

    async def reject(self, action_id: str) -> dict[str, Any]:
        await self.db.run("set_action_props", id=action_id, props={"status": "rejected"})
        await self._emit("action", {"id": action_id, "status": "rejected"})
        return {"action": action_id, "status": "rejected"}

    # ---------------------------------------------------------------- execute
    async def execute(self, action_id: str, approval_token: str) -> dict[str, Any]:
        rows = await self.db.run("get_action", id=action_id)
        if not rows:
            return {"error": f"no action {action_id}"}
        raw = rows[0]["action"]
        if raw.get("status") != "approved" or raw.get("approval_used"):
            return {"error": "action is not approved, or its token was already used"}
        if not approval_token or _hash(approval_token) != raw.get("approval_hash"):
            return {"error": "invalid approval token"}
        if int(raw.get("approval_expires") or 0) < now_ms():
            return {"error": "approval token expired"}
        await self.db.run("set_action_props", id=action_id, props={"approval_used": True, "status": "executing"})
        a = facts._action(raw)
        try:
            result = await self._do(a)
        except Exception as exc:
            await self.db.run("set_action_props", id=action_id, props={"status": "failed", "error": str(exc)})
            await self._emit("action", {"id": action_id, "status": "failed", "error": str(exc)})
            return {"error": f"execution failed: {exc}"}
        await self.db.run("set_action_props", id=action_id, props={
            "status": "executed", "executed_ts": now_ms(), "result": dumps(result), "simulated": self.simulated})
        await self.db.run("set_incident_props", id=a["incident_id"], props={"agent_state": "verifying"})
        await self._emit("action", {"id": action_id, "status": "executed", "result": result})
        if a["kind"] != "page":
            self._spawn(self._verify(a["incident_id"], action_id))
        return {"action": action_id, "status": "executed", "simulated": self.simulated, "result": result,
                "evidence": [a["incident_id"], a["target"]]}

    async def _do(self, a: dict[str, Any]) -> dict[str, Any]:
        if a["kind"] == "page":
            return await pager.page(self.s.rc_data_dir, self.s.pager_webhook_url, a["target"], a["incident_id"],
                                    a.get("reason") or "")
        if self.simulated:
            if self.on_simulated:
                await self.on_simulated(a)
            return {"simulated": True, "kind": a["kind"], "target": a["target"]}
        if a["kind"] == "flag_revert":
            path = self.s.flagd_path
            if not path:
                raise RuntimeError("FLAGD_CONFIG_PATH not set")
            return await asyncio.to_thread(flagd.set_variant, path, a["target"], a["params"]["variant"])
        if a["kind"] == "restart":
            return await containers.restart(self.s.c("demo", "compose_project"), a["target"])
        raise ValueError(f"unknown action kind {a['kind']}")

    # ---------------------------------------------------------------- verify / report
    async def _verify(self, incident_id: str, action_id: str) -> None:
        async def done(inc: str, ok: bool) -> None:
            await self._emit("incident", {"id": inc, "verified": ok})
            if ok:
                await self.write_report(inc)
            else:
                await self.propose(inc)

        await verify.watch(self.db, incident_id, action_id, float(self.s.c("verify", "timeout_seconds", default=90)),
                           self.s.rc_tick_seconds, float(self.s.c("engine", "strong_memory", default=0.6)), done)

    async def verify_recovery(self, incident_id: str) -> dict[str, Any]:
        return await verify.check(self.db, incident_id)

    async def write_report(self, incident_id: str) -> dict[str, Any]:
        out = await report.write(self.db, incident_id, self.narrator)
        await self._emit("report", {"incident": incident_id, "report": out.get("report_id")})
        return out

    async def _get(self, action_id: str) -> dict[str, Any] | None:
        rows = await self.db.run("get_action", id=action_id)
        return facts._action(rows[0]["action"]) if rows else None

    def _spawn(self, coro: Awaitable[Any]) -> None:
        t = asyncio.ensure_future(coro)
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)
