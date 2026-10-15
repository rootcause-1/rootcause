"""Blind chaos runs. One run:
1. all catalogue flags to `off`; wait for no open incidents and 60 s healthy;
2. pick a catalogue entry with a seeded RNG (logged) and flip it as the harness — the engine is not told
   (no API call, no graph write except the flag watcher's normal Change);
3. wait up to 180 s for an incident with an agent verdict, let it settle 45 s (re-investigations), record the
   top-3 hypotheses and the time to the final verdict;
4. revert the flag (as the harness, not the agent) and wait for recovery;
5. score against catalogue truth, run the baselines on the same alert snapshot, write (:ChaosRun) into
   rc_eval_<batch> and regenerate docs/SCORECARD.md.

Runs inside the API process (POST /api/chaos/run). `python -m rootcause.chaos.runner --n 15` asks the API to run
a batch and waits for it (what `make chaos` does). Queries: open_incidents, create_chaos_run, link_chaos_incident.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

from rootcause import facts
from rootcause.actions import flagd
from rootcause.chaos import baselines, scorecard
from rootcause.util import dumps, now_ms

log = logging.getLogger(__name__)
CATALOGUE = Path(__file__).parent / "catalogue.yaml"


def truths(truth: Any) -> list[str]:
    """A catalogue truth is one node id, or a list when a fault has two genuine origins (stored joined by ' | ')."""
    if isinstance(truth, list):
        return [str(t) for t in truth]
    return [t.strip() for t in str(truth).split(" | ")]


def load_catalogue() -> list[dict[str, Any]]:
    return yaml.safe_load(CATALOGUE.read_text(encoding="utf-8")) or []


class ChaosRunner:
    def __init__(self, runtime: Any):
        self.rt = runtime
        self.s = runtime.s
        self.db = runtime.db
        self.state: dict[str, Any] = {"running": False, "batch": None, "done": 0, "total": 0, "current": None}

    async def _wait(self, cond: Any, timeout_s: float, poll_s: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if await cond():
                return True
            await asyncio.sleep(poll_s)
        return False

    async def _no_open(self) -> bool:
        return not await self.db.run("open_incidents")

    async def _healthy_for(self, seconds: float) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            if not await self._no_open():
                return False
            await asyncio.sleep(2)
        return True

    def _set(self, flag: str, variant: str) -> None:
        path = self.s.flagd_path
        if not path:
            raise RuntimeError("FLAGD_CONFIG_PATH is not set")
        flagd.set_variant(path, flag, variant, actor="harness")

    async def run_batch(self, n: int, seed: int, only: str | None = None, mystery: bool = False) -> str:
        batch = f"{time.strftime('%Y%m%d_%H%M%S')}"
        eval_db = self.db.use(f"rc_eval_{batch}")
        cat = [e for e in load_catalogue() if not only or e["flag"] == only]
        rng = random.Random(seed)
        self.state = {"running": True, "batch": batch, "done": 0, "total": n, "current": None, "seed": seed}
        log.info("chaos batch %s: n=%d seed=%d", batch, n, seed)
        try:
            for i in range(n):
                entry = rng.choice(cat)
                self.state["current"] = "mystery" if mystery else entry["flag"]
                run = await self.run_one(entry, f"{batch}-{i + 1:02d}", batch, seed)
                await eval_db.run("create_chaos_run", **run)
                if run["incident_id"]:
                    await eval_db.run("link_chaos_incident", run=run["id"], incident_id=run["incident_id"],
                                      verdict=run["verdict"])
                self.state["done"] = i + 1
                await scorecard.write(eval_db, batch, self.s.rc_docs_dir)
                await self.rt.sse.publish("chaos_run", {**run, "batch": batch})
        finally:
            self.state["running"] = False
            self.state["current"] = None
        return batch

    async def run_one(self, entry: dict[str, Any], run_id: str, batch: str, seed: int) -> dict[str, Any]:
        for e in load_catalogue():
            try:
                if flagd.current_variant(self.s.flagd_path or "", e["flag"]) not in (None, e.get("off", "off")):
                    self._set(e["flag"], e.get("off", "off"))
            except Exception as exc:
                log.warning("reset %s: %s", e["flag"], exc)
        await self._wait(self._no_open, 300)
        await self._healthy_for(60)

        t0 = now_ms()
        self._set(entry["flag"], entry["variant"])
        log.info("chaos %s: %s=%s", run_id, entry["flag"], entry["variant"])

        verdict_inc: dict[str, Any] | None = None

        async def has_verdict() -> bool:
            nonlocal verdict_inc
            # the largest incident opened after the flip (side incidents can open at the same time)
            mine = [i for i in await facts.list_incidents(self.db, "all")
                    if int(i.get("created_ts") or 0) >= t0 and i.get("verdict_ts")]
            if mine:
                verdict_inc = max(mine, key=lambda i: (len(i.get("members") or []), -int(i.get("created_ts") or 0)))
            return bool(mine)

        if await self._wait(has_verdict, 180):
            # the agent re-investigates while signals evolve (e.g. an edge cause appears once traffic is seen to
            # vanish): score the verdict an on-call engineer would act on after a short look, and time it
            await asyncio.sleep(float(self.s.c("chaos", "settle_seconds", default=45)))
            await has_verdict()
        incident_id = verdict_inc["id"] if verdict_inc else None
        hyps: list[dict[str, Any]] = []
        if incident_id:
            full = await facts.incident(self.db, incident_id)
            hyps = (full or {}).get("hypotheses", [])
        ranked = [h["target"] for h in hyps]
        results: dict[str, Any] = {"rootcause": ranked}
        if incident_id:
            results.update(await baselines.run_all(self.db, self.s, incident_id, hyps))

        self._set(entry["flag"], entry.get("off", "off"))
        await self._wait(self._no_open, 180)

        ok = truths(entry["truth"])
        truth = " | ".join(ok)
        verdict = ranked[0] if ranked else None
        top1, top3 = verdict in ok, any(t in ranked[:3] for t in ok)
        miss = None
        if not incident_id:
            miss = "no incident with a verdict within 180 s (fault not visible?)"
        elif not top1:
            pos = [ranked.index(t) + 1 for t in ok if t in ranked]
            miss = f"truth ranked {min(pos)} (top-1 was {verdict})" if pos else f"truth not among candidates (top-1 was {verdict})"
        return {"id": run_id, "batch": batch, "flag": entry["flag"], "variant": entry["variant"], "truth": truth,
                "class": entry.get("class"), "now": now_ms(), "seed": seed, "verdict": verdict, "top1": top1,
                "top3": top3, "ttd_ms": (int(verdict_inc["verdict_ts"]) - t0) if verdict_inc else None,
                "incident_id": incident_id, "results": dumps(results), "miss_reason": miss}


def main() -> None:
    ap = argparse.ArgumentParser(description="Ask the RootCause API to run a blind chaos batch")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--seed", type=int, default=int(time.time()) % 100000)
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()
    r = httpx.post(f"{args.api}/api/chaos/run", json={"n": args.n, "seed": args.seed}, timeout=30)
    print(r.json())
    while True:
        time.sleep(15)
        st = httpx.get(f"{args.api}/api/chaos/status", timeout=10).json()
        print(f"{st['done']}/{st['total']} current={st.get('current')}")
        if not st["running"]:
            break
    print(Path("docs/SCORECARD.md").read_text(encoding="utf-8") if Path("docs/SCORECARD.md").exists() else "")


if __name__ == "__main__":
    main()
