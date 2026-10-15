"""Query registry: loads every named Cypher file in graph/queries/ so code calls queries by name.

File format (see any file in queries/):
    // purpose: one line, copied into docs/QUERIES.md
    // algorithm: FalkorDB algorithm used, or "-"
    <statement>
    ;
    <optional second statement>

Statements are separated by a line holding only `;`. `q("upsert_calls")` returns the list of statements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

QUERY_DIR = Path(__file__).parent / "queries"


@dataclass(frozen=True)
class NamedQuery:
    name: str
    statements: list[str]
    purpose: str = ""
    algorithm: str = "-"
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def is_read_only(self) -> bool:
        words = ("CREATE", "MERGE", "SET ", "DELETE", "REMOVE")
        return not any(w in s.upper() for s in self.statements for w in words)


def parse(name: str, text: str) -> NamedQuery:
    meta: dict[str, str] = {}
    body: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            key, _, value = stripped[2:].partition(":")
            if value:
                meta[key.strip().lower()] = value.strip()
            continue
        body.append(line)
    statements = [s.strip() for s in "\n".join(body).split("\n;") if s.strip().strip(";").strip()]
    statements = [s.rstrip(";").strip() for s in statements]
    return NamedQuery(name, statements, meta.get("purpose", ""), meta.get("algorithm", "-"), meta)


@lru_cache
def load_all() -> dict[str, NamedQuery]:
    return {p.stem: parse(p.stem, p.read_text(encoding="utf-8")) for p in sorted(QUERY_DIR.glob("*.cypher"))}


def q(name: str) -> NamedQuery:
    queries = load_all()
    if name not in queries:
        raise KeyError(f"no query file graph/queries/{name}.cypher")
    return queries[name]
