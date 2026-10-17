"""Codebase in the graph: clone + scan a GitHub repository and write it next to the running system.

    (:Repo)-[:CONTAINS]->(:CodeModule)-[:IMPLEMENTS]->(:Service|:Datastore)
    (:CodeModule)-[:DECLARES {via}]->(:CodeModule)        compose depends_on / *_ADDR env vars
    (:CodeModule)-[:SERVES]->(:RpcService {methods})       .proto files
    (:FeatureFlag)-[:READ_IN {file, line}]->(:CodeModule)  where the code reads a flag
    (:Commit {subject, ts})-[:TOUCHED]->(:CodeModule)      latest commits per module (no author names)

Explanation only: the code tells people *where* to look ("the code behind the root cause"), it never feeds the
ranking. The last scan is cached in data/code_scan.json (like seed.yaml, an input) so it can be written again after
the graph is reset (replay loops); the graph stays the source the UI and tools read.

Queries: code_flags, code_clear, code_upsert_repo, code_upsert_modules, code_upsert_declares, code_upsert_rpc,
code_upsert_flag_reads, code_upsert_commits, code_link_implements, code_for_node, code_modules, code_drift.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from rootcause.codebase import repo
from rootcause.codebase.scan import scan
from rootcause.graph.client import GraphDB
from rootcause.util import now_ms

log = logging.getLogger(__name__)


def cache_path(data_dir: str) -> Path:
    return Path(data_dir) / "code_scan.json"


def _fetch_and_scan(url: str, data_dir: str, flags: list[str]) -> dict[str, Any]:
    """Blocking part (git + file reads), run in a thread."""
    dest = repo.clone(url, data_dir)
    result = scan(dest, flags)
    commits = []
    for m in result["modules"]:
        if m["path"] and m["files"]:
            commits += [c | {"module": m["name"]} for c in repo.module_commits(dest, m["path"])]
    return result | {"url": url, "sha": repo.head(dest), "commits": commits}


async def write(db: GraphDB, data: dict[str, Any], now: int | None = None) -> None:
    rid = "repo:" + "/".join(repo.parse_url(data["url"]))
    await db.run("code_clear")
    await db.run("code_upsert_repo", id=rid, url=data["url"], sha=data["sha"], now=now or now_ms())
    await db.run("code_upsert_modules", id=rid, modules=data["modules"])
    await db.run("code_upsert_declares", declares=data["declares"])
    await db.run("code_upsert_rpc", rpc=data["rpc"])
    await db.run("code_upsert_flag_reads", reads=data["flag_reads"])
    await db.run("code_upsert_commits", commits=data["commits"])
    await db.run("code_link_implements")


async def scan_repo(db: GraphDB, url: str, data_dir: str, known_flags: list[str] | None = None) -> dict[str, Any]:
    """`known_flags`: flag keys from config (seed flag_service_map), added to the ones the graph has seen."""
    repo.parse_url(url)  # fail fast on a bad URL
    flags = sorted({r["id"] for r in await db.run("code_flags")} | set(known_flags or []))
    data = await asyncio.to_thread(_fetch_and_scan, url, data_dir, flags)
    path = cache_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    await write(db, data)
    return summary_of(data)


async def restore(db: GraphDB, data_dir: str) -> bool:
    """Write the cached scan again (after a graph reset)."""
    path = cache_path(data_dir)
    if not path.exists():
        return False
    try:
        await write(db, json.loads(path.read_text(encoding="utf-8")))
        return True
    except Exception as exc:  # a broken cache must never stop the API
        log.warning("could not restore code scan: %s", exc)
        return False


def summary_of(data: dict[str, Any]) -> dict[str, Any]:
    code = [m for m in data["modules"] if m["files"]]
    return {"url": data["url"], "sha": data["sha"], "modules": len(data["modules"]), "code_modules": len(code),
            "loc": sum(m["loc"] for m in code), "declares": len(data["declares"]), "rpc": len(data["rpc"]),
            "flag_reads": len(data["flag_reads"]), "commits": len(data["commits"])}


def _clean(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [r for r in rows or [] if r.get(key) is not None]


async def for_node(db: GraphDB, node_id: str) -> dict[str, Any] | None:
    """The code behind a node (an `edge:A->B` target uses B). None when no scanned module implements it."""
    node = node_id.split("->", 1)[1] if node_id.startswith("edge:") else node_id
    rows = await db.run("code_for_node", node_id=node)
    if not rows:  # services/datastores seen after the scan: link them now
        await db.run("code_link_implements")
        rows = await db.run("code_for_node", node_id=node)
    if not rows:
        return None
    r = rows[0]
    return r | {"node": node, "reads": _clean(r["reads"], "flag"), "commits": _clean(r["commits"], "sha")}


async def overview(db: GraphDB, non_candidates: set[str] | frozenset[str]) -> dict[str, Any]:
    await db.run("code_link_implements")
    modules = await db.run("code_modules")
    drift = [d for d in await db.run("code_drift") if d["src"] not in non_candidates and d["dst"] not in non_candidates]
    head = modules[0] if modules else {}
    return {"repo": head.get("repo"), "sha": head.get("sha"), "scanned_ts": head.get("scanned_ts"),
            "modules": [{k: v for k, v in m.items() if k not in ("repo", "sha", "scanned_ts")} for m in modules],
            "drift": drift}
