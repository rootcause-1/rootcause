"""Replay player: feeds a recorded scenario through the same Pipeline.feed() as live mode, time-shifted to now.

Segments come from the recording's markers: healthy (start..break), broken (break..fix), recovery (fix..end).
`warm()` fast-forwards the healthy segment on a virtual clock instead (public replay site).
The broken segment loops until an approved action matches the recording's fix ({kind, target} on the `fix`
marker); then playback jumps to the recovery segment. `play_fast` drives a virtual clock for golden tests.
No graph queries of its own.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from rootcause.util import now_ms

log = logging.getLogger(__name__)


def load(path: str | Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def segments(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Split a recording into healthy / broken / recovery event lists and read the fix marker."""
    seg: dict[str, list[dict[str, Any]]] = {"healthy": [], "broken": [], "recovery": []}
    current = "healthy"
    fix: dict[str, Any] = {}
    meta: dict[str, Any] = {}
    for ev in events:
        if ev["type"] == "marker":
            name = ev["data"].get("name")
            if name == "start":
                meta = ev["data"]
            elif name == "break":
                current = "broken"
            elif name == "fix":
                current = "recovery"
                fix = {k: v for k, v in ev["data"].items() if k != "name"}
            continue
        seg[current].append(ev)
    return {**seg, "fix": fix, "meta": meta}


def list_scenarios(replay_dir: str) -> list[str]:
    return sorted(p.name.removesuffix(".jsonl.gz") for p in Path(replay_dir).glob("*.jsonl.gz"))


class Player:
    def __init__(self, path: str | Path, feed: Callable[[dict[str, Any], int], Awaitable[None]]):
        self.path = Path(path)
        self.name = self.path.name.removesuffix(".jsonl.gz")
        self.seg = segments(load(self.path))
        self.feed = feed
        self.phase = "idle"
        self.fixed = False
        self.loops = 0
        self.live_tail: list[dict[str, Any]] = []  # end of the healthy segment, played live after warm()

    def status(self) -> dict[str, Any]:
        return {"scenario": self.name, "phase": self.phase, "loops": self.loops, "fixed": self.fixed,
                "expected_fix": self.seg["fix"]}

    def notify_action(self, action: dict[str, Any]) -> None:
        fix = self.seg["fix"]
        if fix and action.get("kind") == fix.get("kind") and action.get("target") == fix.get("target"):
            log.info("replay: approved action matches the recorded fix -> recovery")
            self.fixed = True

    async def _play(self, events: list[dict[str, Any]], stop_on_fix: bool) -> bool:
        if not events:
            return False
        offset = now_ms() - int(events[0]["ts"])
        for ev in events:
            if stop_on_fix and self.fixed:
                return True
            wait = (int(ev["ts"]) + offset - now_ms()) / 1000
            if wait > 0:
                await asyncio.sleep(wait)
            await self.feed(ev, offset)
        return False

    async def warm(self, tick: Callable[[int], Awaitable[Any]], tick_ms: int, live_tail_ms: int = 0) -> None:
        """Fast-forward the healthy segment on a virtual clock that ends *now*, so baselines are learned in
        seconds instead of minutes (visitors of the public replay site should not wait 3 minutes).
        The last `live_tail_ms` of healthy traffic is kept back and played live by run(), so a visitor sees the
        shop working normally before the fault starts."""
        self.phase = "warming"
        events = self.seg["healthy"]
        if events and live_tail_ms > 0:
            cutoff = int(events[-1]["ts"]) - live_tail_ms
            self.live_tail = [e for e in events if int(e["ts"]) > cutoff]
            events = [e for e in events if int(e["ts"]) <= cutoff]
        if not events:
            return
        offset = now_ms() - int(events[-1]["ts"])
        next_tick = int(events[0]["ts"]) + offset + tick_ms
        for ev in events:
            while int(ev["ts"]) + offset >= next_tick:
                await tick(next_tick)
                next_tick += tick_ms
            await self.feed(ev, offset)
        await tick(next_tick)

    async def run(self, warmed: bool = False, max_loops: int | None = None) -> None:
        """Play the scenario. With `max_loops`, give up on the broken segment after that many loops without the
        matching fix (phase 'expired') so an unattended public site starts over instead of piling up incidents."""
        self.phase = "healthy"
        await self._play(self.live_tail if warmed else self.seg["healthy"], stop_on_fix=False)
        self.phase = "broken"
        while not self.fixed:
            if await self._play(self.seg["broken"], stop_on_fix=True):
                break
            self.loops += 1
            if max_loops is not None and self.loops >= max_loops:
                self.phase = "expired"
                return
            if not self.seg["broken"]:
                await asyncio.sleep(1)
        self.phase = "recovery"
        await self._play(self.seg["recovery"], stop_on_fix=False)
        self.phase = "finished"


async def play_fast(path: str | Path, feed: Callable[[dict[str, Any], int], Awaitable[None]],
                    tick: Callable[[int], Awaitable[Any]], tick_ms: int, segments_to_play: tuple[str, ...] =
                    ("healthy", "broken"), until: Callable[[], Awaitable[bool]] | None = None) -> int:
    """Virtual clock: replay events in order and call tick(t) every tick_ms of recorded time. Returns ticks run."""
    seg = segments(load(path))
    events = [ev for name in segments_to_play for ev in seg[name]]
    if not events:
        return 0
    t = int(events[0]["ts"])
    next_tick = t + tick_ms
    ticks = 0
    for ev in events:
        while int(ev["ts"]) >= next_tick:
            await tick(next_tick)
            ticks += 1
            next_tick += tick_ms
            if until and await until():
                return ticks
        await feed(ev, 0)
    return ticks
