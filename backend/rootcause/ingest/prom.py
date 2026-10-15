"""PromQL poller: runs the queries listed in config/rootcause.yaml (prometheus.queries) and turns each series into
a property on a graph node (e.g. Kafka lag -> Queue.lag, runtime memory -> Service.runtime_mem_mb).

Metric names are never guessed: a query left as `null` in the config is skipped with a warning.
The pipeline writes the samples with the `set_node_props` query.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


def series_to_rows(result: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Prometheus vector result -> [{id, props}] using the spec's label / target_prefix / prop / scale."""
    rows = []
    for series in result:
        name = series.get("metric", {}).get(spec["label"])
        if not name:
            continue
        try:
            value = float(series["value"][1]) * float(spec.get("scale", 1.0))
        except (KeyError, ValueError, IndexError):
            continue
        rows.append({"id": f"{spec.get('target_prefix', '')}{name}", "props": {spec["prop"]: value}})
    return rows


class PromSource:
    def __init__(self, url: str | None, queries: dict[str, Any]):
        self.url = url
        self.queries = {k: v for k, v in (queries or {}).items() if v}
        skipped = [k for k, v in (queries or {}).items() if not v]
        if skipped:
            log.warning("prometheus queries not configured yet (VERIFY): %s", ", ".join(skipped))
        self._client = httpx.AsyncClient(timeout=3.0)

    async def poll(self) -> list[dict[str, Any]]:
        if not self.url or not self.queries:
            return []
        rows: list[dict[str, Any]] = []
        for name, spec in self.queries.items():
            try:
                r = await self._client.get(f"{self.url}/api/v1/query", params={"query": spec["promql"]})
                r.raise_for_status()
                rows.extend(series_to_rows(r.json()["data"]["result"], spec))
            except Exception as exc:
                log.debug("prom query %s failed: %s", name, exc)
        return rows
