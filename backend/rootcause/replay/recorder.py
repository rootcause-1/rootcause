"""Recorder: tees every engine input (OTLP batches, metric samples, docker stats/events, flag configs) with its
timestamp to replay/<scenario>.jsonl.gz, plus `marker` events for segment boundaries
(healthy -> break -> broken -> fix -> recovery). No graph queries.
"""

from __future__ import annotations

import gzip
import json
import threading
from pathlib import Path
from typing import Any

from rootcause.util import now_ms


class Recorder:
    def __init__(self, replay_dir: str):
        self.dir = Path(replay_dir)
        self._fh: Any = None
        self.scenario: str | None = None
        self.events = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self._fh is not None

    def start(self, scenario: str, meta: dict[str, Any] | None = None) -> str:
        self.stop()
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{scenario}.jsonl.gz"
        self._fh = gzip.open(path, "wt", encoding="utf-8")
        self.scenario = scenario
        self.events = 0
        self.marker("start", meta or {})
        return str(path)

    def write(self, ev: dict[str, Any]) -> None:
        if self._fh is None:
            return
        with self._lock:
            self._fh.write(json.dumps(ev, separators=(",", ":")) + "\n")
            self.events += 1

    def marker(self, name: str, data: dict[str, Any] | None = None) -> None:
        self.write({"type": "marker", "ts": now_ms(), "data": {"name": name, **(data or {})}})

    def stop(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.close()
                self._fh = None
