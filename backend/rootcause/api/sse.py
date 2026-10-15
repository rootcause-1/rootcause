"""Server-sent events for the UI (`GET /api/stream`): graph_delta, alert, incident, step, action, chaos_run, tick.

In-process fan-out only (each subscriber gets an asyncio.Queue); nothing is stored here. No graph queries.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any


class Broadcaster:
    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[str]] = set()

    async def publish(self, event: str, data: Any) -> None:
        msg = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
        for q in list(self.subscribers):
            if q.qsize() > 200:  # slow client: drop it rather than grow without bound
                self.subscribers.discard(q)
                continue
            q.put_nowait(msg)

    async def stream(self) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self.subscribers.add(q)
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                try:
                    yield await asyncio.wait_for(q.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self.subscribers.discard(q)
