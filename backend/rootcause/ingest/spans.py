"""Span window aggregation: client/server pairing, self-error attribution, messaging, datastores, journeys, agent runs.

Pure logic (no graph access). `SpanWindow` is the short-lived in-process buffer for the 60 s window; every tick
`aggregate(now_ms)` turns it into row lists for these queries: upsert_services, upsert_calls, upsert_messaging,
upsert_uses, upsert_journeys, set_node_props (agent metrics) and upsert_flag_affects (services that evaluate a flag). The graph stays the source of truth.

Rules (CLAUDE.md §7.1):
- CLIENT span in A whose child SERVER span is in B -> call A->B. No child server span -> name B from
  peer.service / rpc.service (via aliases) / server.address and count the call as `unanswered`.
- CLIENT span with db.system -> USES edge to a datastore (`db:<name>` or `cache:<host>`).
- PRODUCER -> PRODUCES_TO queue, CONSUMER -> CONSUMED_BY.
- Self-error: an error span (server/internal/consumer) whose children in the window are all non-error.
- Spans are only aggregated once they are `finalise_lag_ms` old, so late children can still arrive.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from rootcause.ingest.otlp import CLIENT, CONSUMER, INTERNAL, PRODUCER, SERVER, Span


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return float(s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))])


@dataclass
class IngestConfig:
    window_ms: int = 60_000
    finalise_lag_ms: int = 10_000
    peer_aliases: dict[str, str] = field(default_factory=dict)
    cache_systems: tuple[str, ...] = ("redis", "valkey")
    journey_root_services: tuple[str, ...] = ("frontend-proxy", "frontend")
    journeys: list[dict[str, Any]] = field(default_factory=list)  # [{id, routes}]
    journey_critical_share: float = 0.9
    agent_workflow_span: str = "astronomy_shop_agent_workflow"
    non_candidates: frozenset[str] = frozenset()
    op_min_spans: int = 2              # routes with fewer server spans in the window are too noisy to rate
    op_min_latency_spans: int = 5      # ... and too few to take a p95 of


@dataclass
class WindowStats:
    services: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    produces: list[dict[str, Any]] = field(default_factory=list)
    consumes: list[dict[str, Any]] = field(default_factory=list)
    queues: list[dict[str, Any]] = field(default_factory=list)
    uses: list[dict[str, Any]] = field(default_factory=list)
    stores: list[dict[str, Any]] = field(default_factory=list)
    journeys: list[dict[str, Any]] = field(default_factory=list)
    requires: list[dict[str, Any]] = field(default_factory=list)
    agent_props: list[dict[str, Any]] = field(default_factory=list)
    flag_affects: list[dict[str, Any]] = field(default_factory=list)  # [{flag, svc}] from flag evaluation events
    span_count: int = 0


def _protocol(span: Span) -> str:
    a = span.attrs
    if a.get("rpc.system") or a.get("rpc.system.name"):
        return str(a.get("rpc.system") or a.get("rpc.system.name"))
    if a.get("messaging.system"):
        return str(a["messaging.system"])
    if any(k in a for k in ("http.request.method", "http.method", "url.full", "http.url", "http.protocol")):
        return "http"
    return "unknown"


def _route(span: Span) -> str:
    a = span.attrs
    for key in ("http.route", "url.path", "http.target", "http.url", "url.full"):
        if a.get(key):
            value = str(a[key])
            if "://" in value:  # full url -> path
                value = "/" + value.split("://", 1)[1].split("/", 1)[-1]
            return value.split("?", 1)[0]
    return span.name


def _status(span: Span) -> int | None:
    code = span.attrs.get("http.response.status_code", span.attrs.get("http.status_code"))
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _handler_failed(span: Span, children: dict[str, list[Span]]) -> bool:
    """Did the request fail? Error status, a 5xx, or a 4xx whose own handler (same-service descendant) errored.
    The demo frontend answers a failed checkout with HTTP 422 and records the exception on an inner span."""
    if span.error:
        return True
    code = _status(span)
    if code is None or code < 400:
        return False
    if code >= 500:
        return True
    stack = list(children.get(span.span_id, []))
    while stack:
        k = stack.pop()
        if k.service != span.service:
            continue
        if k.error:
            return True
        stack.extend(children.get(k.span_id, []))
    return False


class SpanWindow:
    """Short-lived buffer of recent spans keyed by trace."""

    def __init__(self, cfg: IngestConfig):
        self.cfg = cfg
        self.traces: dict[str, list[Span]] = defaultdict(list)

    def add(self, spans: list[Span]) -> None:
        for s in spans:
            self.traces[s.trace_id].append(s)

    def prune(self, now_ms: int) -> None:
        horizon = now_ms - self.cfg.window_ms - self.cfg.finalise_lag_ms
        for tid in list(self.traces):
            kept = [s for s in self.traces[tid] if s.end_ms >= horizon]
            if kept:
                self.traces[tid] = kept
            else:
                del self.traces[tid]

    def aggregate(self, now_ms: int) -> WindowStats:
        self.prune(now_ms)
        hi = now_ms - self.cfg.finalise_lag_ms
        lo = hi - self.cfg.window_ms
        return aggregate_traces(self.traces, lo, hi, self.cfg)


def _peer_name(span: Span, aliases: dict[str, str], known: set[str]) -> str | None:
    a = span.attrs
    if a.get("peer.service"):
        return aliases.get(str(a["peer.service"]), str(a["peer.service"]))
    # rpc.service (old semconv) or the service part of rpc.method ("oteldemo.PaymentService/Charge", new semconv);
    # this names the callee even when the client dialled an unknown host (e.g. checkout -> "badAddress")
    rs = a.get("rpc.service") or (str(a["rpc.method"]).rsplit("/", 1)[0] if "/" in str(a.get("rpc.method", "")) else None)
    if rs and str(rs) in aliases:
        return aliases[str(rs)]
    for key in ("server.address", "net.peer.name"):
        host = a.get(key)
        if host:
            host = str(host)
            if host in aliases:
                return aliases[host]
            if host in known:
                return host
    return None


def aggregate_traces(traces: dict[str, list[Span]], lo: int, hi: int, cfg: IngestConfig) -> WindowStats:
    secs = max(1.0, (hi - lo) / 1000.0)
    known_services = {s.service for spans in traces.values() for s in spans}

    svc_server: Counter[str] = Counter()
    svc_server_err: Counter[str] = Counter()
    svc_self_err: Counter[str] = Counter()
    svc_lat: dict[str, list[float]] = defaultdict(list)
    op_n: Counter[tuple[str, str]] = Counter()
    op_err: Counter[tuple[str, str]] = Counter()
    op_lat: dict[tuple[str, str], list[float]] = defaultdict(list)
    svc_any: set[str] = set()

    call_n: Counter[tuple[str, str]] = Counter()
    call_err: Counter[tuple[str, str]] = Counter()
    call_unans: Counter[tuple[str, str]] = Counter()
    call_lat: dict[tuple[str, str], list[float]] = defaultdict(list)
    call_proto: dict[tuple[str, str], str] = {}

    prod: Counter[tuple[str, str]] = Counter()
    cons: Counter[tuple[str, str]] = Counter()
    cons_group: dict[tuple[str, str], str] = {}

    uses_n: Counter[tuple[str, str]] = Counter()
    uses_err: Counter[tuple[str, str]] = Counter()
    uses_lat: dict[tuple[str, str], list[float]] = defaultdict(list)
    uses_sys: dict[str, str] = {}

    j_total: Counter[str] = Counter()
    j_ok: Counter[str] = Counter()
    j_touch: dict[str, Counter[str]] = defaultdict(Counter)

    agent_runs: dict[str, list[tuple[int, int]]] = defaultdict(list)  # service -> [(tool_calls, llm_calls)]
    agent_llm_lat: dict[str, list[float]] = defaultdict(list)

    flag_evals: set[tuple[str, str]] = set()

    count = 0
    for spans in traces.values():
        by_id = {s.span_id: s for s in spans}
        children: dict[str, list[Span]] = defaultdict(list)
        for s in spans:
            if s.parent_id:
                children[s.parent_id].append(s)

        in_window = [s for s in spans if lo <= s.end_ms < hi]
        count += len(in_window)
        for s in in_window:
            svc_any.add(s.service)
            kids = children.get(s.span_id, [])
            for key in s.flag_keys:
                if s.service not in cfg.non_candidates:
                    flag_evals.add((key, s.service))

            if s.kind == SERVER:
                failed = _handler_failed(s, children)
                svc_server[s.service] += 1
                svc_lat[s.service].append(s.duration_ms)
                op = (s.service, _route(s))
                op_n[op] += 1
                op_lat[op].append(s.duration_ms)
                if failed:
                    svc_server_err[s.service] += 1
                    op_err[op] += 1
            if s.error and s.kind in (SERVER, INTERNAL, CONSUMER) and not any(k.error for k in kids):
                svc_self_err[s.service] += 1

            if s.kind == CLIENT:
                db_system = s.attrs.get("db.system") or s.attrs.get("db.system.name")
                if db_system:
                    ds = _datastore_id(s, str(db_system), cfg)
                    key = (s.service, ds)
                    uses_n[key] += 1
                    uses_lat[key].append(s.duration_ms)
                    uses_sys[ds] = str(db_system)
                    if s.error:
                        uses_err[key] += 1
                    continue
                server_kids = [k for k in kids if k.kind == SERVER and k.service != s.service]
                if server_kids:
                    dst = server_kids[0].service
                    unanswered = False
                else:
                    dst = _peer_name(s, cfg.peer_aliases, known_services)
                    unanswered = True
                if not dst or dst == s.service:
                    continue
                key = (s.service, dst)
                call_n[key] += 1
                call_lat[key].append(s.duration_ms)
                call_proto.setdefault(key, _protocol(s))
                if s.error:
                    call_err[key] += 1
                if unanswered:
                    call_unans[key] += 1

            elif s.kind == PRODUCER:
                q = _queue_id(s)
                if q:
                    prod[(s.service, q)] += 1
            elif s.kind == CONSUMER:
                q = _queue_id(s)
                if q:
                    cons[(q, s.service)] += 1
                    group = (s.attrs.get("messaging.consumer.group.name") or s.attrs.get("messaging.kafka.consumer.group")
                             or s.attrs.get("messaging.kafka.consumer_group"))
                    if group:
                        cons_group[(q, s.service)] = str(group)

            if s.name == cfg.agent_workflow_span or s.name.startswith(cfg.agent_workflow_span + "."):
                tools, llms = _agent_children(s, children)
                agent_runs[s.service].append((len(tools), len(llms)))
                agent_llm_lat[s.service].extend(x.duration_ms for x in llms)

        # journeys: entry spans at the frontend / proxy. An entry span has no parent, or its parent belongs to a
        # service outside the shop (the load generator or the browser, which are traced too).
        for s in in_window:
            if s.service not in cfg.journey_root_services:
                continue
            if s.parent_id:
                parent = by_id.get(s.parent_id)
                if parent is None or parent.service in cfg.journey_root_services:
                    continue
            journey = match_journey(_route(s), cfg.journeys)
            if not journey:
                continue
            j_total[journey] += 1
            if not _handler_failed(s, children):
                j_ok[journey] += 1
            for svc in {x.service for x in spans}:
                j_touch[journey][svc] += 1

    # worst endpoint per service: a failing low-traffic route (e.g. /api/checkout) is invisible in the service-wide
    # error rate of a busy frontend, so the detector also watches the max per-route error rate
    op_worst: dict[str, float] = defaultdict(float)
    op_slowest: dict[str, float] = {}
    for (svc, _op), n in op_n.items():
        if n >= cfg.op_min_spans:
            op_worst[svc] = max(op_worst[svc], op_err[(svc, _op)] / n)
        if n >= cfg.op_min_latency_spans:  # likewise the slowest route's p95 (one slow route in a busy service)
            op_slowest[svc] = max(op_slowest.get(svc, 0.0), p95(op_lat[(svc, _op)]) or 0.0)

    st = WindowStats(span_count=count)
    st.flag_affects = [{"flag": f, "svc": svc} for f, svc in sorted(flag_evals)]
    for svc in sorted(svc_any):
        n = svc_server[svc]
        st.services.append({
            "id": svc,
            "rps": n / secs,
            "err_rate": (svc_server_err[svc] / n) if n else 0.0,
            "op_err_rate": op_worst.get(svc, 0.0),
            "op_p95_ms": op_slowest.get(svc),
            "self_err_rate": min(1.0, svc_self_err[svc] / n) if n else (1.0 if svc_self_err[svc] else 0.0),
            "p95_ms": p95(svc_lat[svc]),
            "server_spans": n,
        })
    for (a, b), n in sorted(call_n.items()):
        st.calls.append({
            "src": a, "dst": b, "protocol": call_proto.get((a, b), "unknown"), "rps": n / secs,
            "err_rate": call_err[(a, b)] / n, "p95_ms": p95(call_lat[(a, b)]),
            "unanswered_rate": call_unans[(a, b)] / secs,
            "unanswered_share": call_unans[(a, b)] / n,  # share of calls no server span answered
        })
    queues: dict[str, dict[str, float]] = defaultdict(lambda: {"produce_rate": 0.0, "consume_rate": 0.0})
    for (svc, q), n in sorted(prod.items()):
        st.produces.append({"svc": svc, "queue": q, "rate": n / secs})
        queues[q]["produce_rate"] += n / secs
    for (q, svc), n in sorted(cons.items()):
        st.consumes.append({"queue": q, "svc": svc, "rate": n / secs, "group": cons_group.get((q, svc), "")})
        queues[q]["consume_rate"] += n / secs
    st.queues = [{"queue": q, **v} for q, v in sorted(queues.items())]

    store_n: Counter[str] = Counter()
    store_err: Counter[str] = Counter()
    store_lat: dict[str, list[float]] = defaultdict(list)
    for (svc, ds), n in sorted(uses_n.items()):
        st.uses.append({"svc": svc, "ds": ds, "system": uses_sys[ds], "rps": n / secs,
                        "err_rate": uses_err[(svc, ds)] / n, "p95_ms": p95(uses_lat[(svc, ds)])})
        store_n[ds] += n
        store_err[ds] += uses_err[(svc, ds)]
        store_lat[ds].extend(uses_lat[(svc, ds)])
    st.stores = [{"ds": ds, "rps": n / secs, "err_rate": store_err[ds] / n, "p95_ms": p95(store_lat[ds])}
                 for ds, n in sorted(store_n.items())]

    for j, n in sorted(j_total.items()):
        st.journeys.append({"id": j, "success_rate": j_ok[j] / n, "rps": n / secs})
        for svc, touched in sorted(j_touch[j].items()):
            if svc in cfg.non_candidates:
                continue
            share = touched / n
            st.requires.append({"journey": j, "svc": svc, "share": share,
                                "critical": share >= cfg.journey_critical_share})

    for svc, runs in sorted(agent_runs.items()):
        st.agent_props.append({"id": svc, "props": {
            "agent_runs": len(runs),
            "tool_calls_per_run": sum(t for t, _ in runs) / len(runs),
            "llm_calls_per_run": sum(llm for _, llm in runs) / len(runs),
            "llm_p95_ms": p95(agent_llm_lat[svc]),
        }})
    return st


def _datastore_id(span: Span, system: str, cfg: IngestConfig) -> str:
    a = span.attrs
    if system.lower() in cfg.cache_systems:
        host = a.get("server.address") or a.get("net.peer.name") or system
        return f"cache:{host}"
    # the server host names the store consistently across clients (db.name / db.namespace differ per client)
    name = a.get("server.address") or a.get("net.peer.name") or a.get("db.name") or a.get("db.namespace") or system
    return f"db:{name}"


def _queue_id(span: Span) -> str | None:
    a = span.attrs
    name = a.get("messaging.destination.name") or a.get("messaging.destination") or a.get("messaging.kafka.topic")
    return f"queue:{name}" if name else None


def _agent_children(root: Span, children: dict[str, list[Span]]) -> tuple[list[Span], list[Span]]:
    """Descendants of an agent workflow span that are tool calls / LLM calls (gen_ai semantic conventions)."""
    tools: list[Span] = []
    llms: list[Span] = []
    stack = list(children.get(root.span_id, []))
    while stack:
        s = stack.pop()
        op = str(s.attrs.get("gen_ai.operation.name", ""))
        if op == "execute_tool" or s.name.startswith("execute_tool"):
            tools.append(s)
        elif op in ("chat", "text_completion", "generate_content") or (
                "gen_ai.request.model" in s.attrs and s.kind == CLIENT):
            llms.append(s)
        stack.extend(children.get(s.span_id, []))
    return tools, llms


def match_journey(route: str, journeys: list[dict[str, Any]]) -> str | None:
    """Longest-prefix match of a route against journey routes ("/" only matches exactly)."""
    best: tuple[int, str] | None = None
    for j in journeys:
        for r in j.get("routes", []):
            hit = route == r if r == "/" else route.startswith(r)
            if hit and (best is None or len(r) > best[0]):
                best = (len(r), j["id"])
    return best[1] if best else None
