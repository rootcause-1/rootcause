"""FalkorDB connection and graph selection (rc_live / rc_replay / rc_eval_*).

`GraphDB.run("name", **params)` executes a named query from graph/queries/ (all of its statements in order)
and returns the rows of the last statement as dicts. `ro()` uses GRAPH.RO_QUERY with a timeout.
`raw()` exists only for schema bootstrapping (CREATE INDEX) and the read-only `cypher_readonly` tool.
"""

from __future__ import annotations

import logging
from typing import Any

from falkordb.asyncio import FalkorDB

from rootcause.graph.registry import q
from rootcause.settings import get_settings

log = logging.getLogger(__name__)


def _plain(value: Any) -> Any:
    """Turn FalkorDB Node/Edge/Path objects into plain JSON-able values."""
    if hasattr(value, "labels") and hasattr(value, "properties"):  # Node
        return {"_labels": list(value.labels or []), **dict(value.properties or {})}
    if hasattr(value, "relation") and hasattr(value, "properties"):  # Edge
        return {"_type": value.relation, **dict(value.properties or {})}
    if hasattr(value, "nodes") and callable(value.nodes):  # Path
        return [_plain(n) for n in value.nodes()]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _rows(result: Any) -> list[dict[str, Any]]:
    header = [h[1] if isinstance(h, (list, tuple)) else h for h in (result.header or [])]
    header = [h.decode() if isinstance(h, bytes) else h for h in header]
    return [dict(zip(header, (_plain(v) for v in row), strict=False)) for row in (result.result_set or [])]


class GraphDB:
    """One selected graph on one FalkorDB connection."""

    def __init__(self, name: str | None = None, db: FalkorDB | None = None):
        s = get_settings()
        self.name = name or s.rc_graph
        self._db = db or FalkorDB(host=s.falkordb_host, port=s.falkordb_port)
        self.g = self._db.select_graph(self.name)

    def use(self, name: str) -> GraphDB:
        """Same connection, different graph (e.g. rc_eval_<batch>)."""
        return GraphDB(name, self._db)

    async def run(self, name: str, **params: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for stmt in q(name).statements:
            try:
                rows = _rows(await self.g.query(stmt, params or None))
            except Exception as exc:  # include the query name: much easier to debug
                raise RuntimeError(f"query {name!r} failed: {exc}") from exc
        return rows

    async def ro(self, name: str, timeout_ms: int = 2000, **params: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for stmt in q(name).statements:
            rows = _rows(await self.g.ro_query(stmt, params or None, timeout=timeout_ms))
        return rows

    async def raw(self, query: str, params: dict[str, Any] | None = None, read_only: bool = False,
                  timeout_ms: int | None = None) -> list[dict[str, Any]]:
        if read_only:
            return _rows(await self.g.ro_query(query, params, timeout=timeout_ms))
        return _rows(await self.g.query(query, params))

    async def delete(self) -> None:
        try:
            await self.g.delete()
        except Exception as exc:  # graph may not exist yet
            log.debug("delete %s: %s", self.name, exc)

    async def close(self) -> None:
        try:
            await self._db.aclose()
        except Exception:  # older clients: connection pool closes with the process
            pass


_default: GraphDB | None = None


def get_graph() -> GraphDB:
    global _default
    if _default is None:
        _default = GraphDB()
    return _default


def set_graph(db: GraphDB) -> None:
    """Used by tests and replay to point the whole app at another graph."""
    global _default
    _default = db
