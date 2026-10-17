"""Root-cause ranking: five signals, each normalised to 0-1, combined with weights from rootcause.yaml.

    score = 0.30*depth + 0.25*self + 0.20*pagerank + 0.15*change + 0.10*memory
    depth    = 1.0 if out_degree == 0 else 0.5 ** out_degree        (blame_depth, blame_targets)
               a changed service does not count a passive datastore it blames (no change, no resource alarm of
               its own) as "something further to blame": the database slowed down because of it (passive_targets)
    self     = self_err_rate / max in incident, or the anomaly z-score/3 capped at 1 for non-error alerts
    pagerank = PageRank over BLAMES / max in incident                 (pagerank_blame, algo.pageRank)
    change   = 1.0 if a change hit the node <= 10 min before onset, 0.5 if <= 30 min (recent_changes_for)
    memory   = best similarity of a resolved past incident whose root was this node (similar_incidents)

Pure functions; engine/core.py gathers the inputs with the queries named above.
`disabled` switches signals off (the chaos `graph_off` baseline uses only `self`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SIGNALS = ("depth", "self", "pagerank", "change", "memory")


@dataclass
class Candidate:
    target: str                      # node id, or "edge:A->B"
    node: str                        # node the ROOT_CAUSE edge points at
    depth: float = 0.0
    self: float = 0.0
    pagerank: float = 0.0
    change: float = 0.0
    memory: float = 0.0
    score: float = 0.0
    rank: int = 0
    changes: list[dict[str, Any]] = field(default_factory=list)
    edge: str | None = None
    explains: list[str] = field(default_factory=list)  # passive datastores this candidate's change explains

    def signals(self) -> dict[str, float]:
        return {s: round(getattr(self, s), 4) for s in SIGNALS}


def depth_score(out_degree: int) -> float:
    return 1.0 if out_degree <= 0 else 0.5 ** out_degree


RESOURCE_KINDS = {"cpu", "memory", "gc"}


def passive_targets(targets: list[str], is_datastore: dict[str, bool], changed: dict[str, float],
                    alert_kinds: dict[str, set[str]]) -> list[str]:
    """Blame targets that are only symptoms of a changed caller: datastores with no change of their own and no
    resource alarm (cpu / memory / gc). A database cannot break itself without one of those; if the service that
    uses it changed just before, the slow database is that change's effect, not something further to blame."""
    return [d for d in targets if is_datastore.get(d) and changed.get(d, 0.0) == 0.0
            and not (alert_kinds.get(d, set()) & RESOURCE_KINDS)]


def zscore_self(value: float, baseline: float | None, dev: float | None) -> float:
    base = float(baseline or 0.0)
    spread = max(float(dev or 0.0), 0.05 * abs(base), 1e-9)
    return max(0.0, min(1.0, (float(value) - base) / spread / 3.0))


def change_score(change_ts: list[int], onset_ms: int, strong_min: float, weak_min: float) -> float:
    best = 0.0
    for ts in change_ts:
        before_min = (onset_ms - ts) / 60_000.0
        if before_min < -0.5:  # more than 30 s after onset: not a cause
            continue
        if before_min <= strong_min:
            best = max(best, 1.0)
        elif before_min <= weak_min:
            best = max(best, 0.5)
    return best


def self_signal(node: str, alerts: list[dict[str, Any]], self_err: dict[str, float]) -> float:
    """Error alerts use self_err_rate normalised in the incident; other alerts use the capped z-score."""
    mine = [a for a in alerts if a["target"] == node]
    max_self = max(self_err.values(), default=0.0)
    best = 0.0
    for a in mine:
        if a["kind"] == "error_rate":
            best = max(best, (self_err.get(node, 0.0) / max_self) if max_self > 0 else 0.0)
        else:
            best = max(best, zscore_self(a.get("value") or 0.0, a.get("baseline"), a.get("dev")))
    return best


def score(c: Candidate, weights: dict[str, float], disabled: set[str] | None = None) -> float:
    off = disabled or set()
    return sum(weights.get(s, 0.0) * getattr(c, s) for s in SIGNALS if s not in off)


def rank(cands: list[Candidate], weights: dict[str, float], disabled: set[str] | None = None) -> list[Candidate]:
    for c in cands:
        c.score = round(score(c, weights, disabled), 4)
    # ties: deeper first, then name (deterministic)
    ordered = sorted(cands, key=lambda c: (-c.score, -c.depth, c.target))
    for i, c in enumerate(ordered, start=1):
        c.rank = i
    return ordered


def normalise(values: dict[str, float], keys: list[str]) -> dict[str, float]:
    sub = {k: float(values.get(k, 0.0) or 0.0) for k in keys}
    top = max(sub.values(), default=0.0)
    return {k: (v / top if top > 0 else 0.0) for k, v in sub.items()}
