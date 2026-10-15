"""Span pairing, unanswered calls, self-error attribution, messaging, datastores, journeys, agent runs."""

from rootcause.ingest.otlp import CLIENT, CONSUMER, INTERNAL, PRODUCER, SERVER, Span, parse_otlp_json
from rootcause.ingest.spans import IngestConfig, SpanWindow, aggregate_traces, match_journey

CFG = IngestConfig(
    window_ms=60_000, finalise_lag_ms=0,
    peer_aliases={"oteldemo.PaymentService": "payment"},
    journeys=[{"id": "journey:checkout", "routes": ["/api/checkout"]}, {"id": "journey:browse", "routes": ["/"]}],
)


def sp(tid, sid, parent, svc, kind, err=False, t=1000, dur=10, name="op", **attrs):
    return Span(tid, sid, parent, svc, name, kind, t, t + dur, err, attrs)


def run(spans, cfg=CFG):
    traces = {}
    for s in spans:
        traces.setdefault(s.trace_id, []).append(s)
    return aggregate_traces(traces, 0, 60_000, cfg)


def test_client_server_pairing_makes_call_edge():
    st = run([
        sp("t", "1", "", "frontend", SERVER),
        sp("t", "2", "1", "frontend", CLIENT, **{"rpc.system": "grpc"}),
        sp("t", "3", "2", "checkout", SERVER),
    ])
    calls = {(c["src"], c["dst"]): c for c in st.calls}
    assert ("frontend", "checkout") in calls
    assert calls[("frontend", "checkout")]["protocol"] == "grpc"
    assert calls[("frontend", "checkout")]["unanswered_rate"] == 0


def test_unanswered_call_named_via_rpc_alias():
    st = run([
        sp("t", "1", "", "checkout", SERVER, err=True),
        sp("t", "2", "1", "checkout", CLIENT, err=True, **{"rpc.service": "oteldemo.PaymentService",
                                                              "server.address": "badAddress"}),
    ])
    c = st.calls[0]
    assert (c["src"], c["dst"]) == ("checkout", "payment")
    assert c["unanswered_rate"] > 0 and c["err_rate"] == 1.0


def test_self_error_only_where_error_originates():
    st = run([
        sp("t", "1", "", "frontend", SERVER, err=True),
        sp("t", "2", "1", "frontend", CLIENT, err=True),
        sp("t", "3", "2", "payment", SERVER, err=True),  # no erroring children -> self error
    ])
    svc = {s["id"]: s for s in st.services}
    assert svc["payment"]["self_err_rate"] == 1.0
    assert svc["frontend"]["self_err_rate"] == 0.0
    assert svc["frontend"]["err_rate"] == 1.0


def test_internal_child_error_moves_self_error_down():
    st = run([
        sp("t", "1", "", "payment", SERVER, err=True),
        sp("t", "2", "1", "payment", INTERNAL, err=True),
    ])
    # the internal span is the origin; the server span has an erroring child
    assert st.services[0]["self_err_rate"] == 1.0  # 1 self error / 1 server span


def test_messaging_and_db():
    st = run([
        sp("t", "1", "", "checkout", PRODUCER, **{"messaging.destination.name": "orders"}),
        sp("t", "2", "1", "accounting", CONSUMER, **{"messaging.destination.name": "orders",
                                                     "messaging.consumer.group.name": "accounting"}),
        sp("u", "1", "", "cart", CLIENT, **{"db.system": "redis", "server.address": "valkey-cart"}),
    ])
    assert st.produces[0]["queue"] == "queue:orders"
    assert st.consumes[0]["svc"] == "accounting" and st.consumes[0]["group"] == "accounting"
    assert st.uses[0]["ds"] == "cache:valkey-cart"
    assert st.queues[0]["produce_rate"] > 0 and st.queues[0]["consume_rate"] > 0


def test_journey_success_and_requires():
    st = run([
        sp("t", "1", "", "frontend-proxy", SERVER, **{"http.route": "/api/checkout",
                                                      "http.response.status_code": 500}),
        sp("t", "2", "1", "checkout", SERVER),
        sp("u", "1", "", "frontend-proxy", SERVER, **{"url.path": "/api/checkout"}),
    ])
    j = st.journeys[0]
    assert j["id"] == "journey:checkout" and j["success_rate"] == 0.5
    req = {r["svc"]: r for r in st.requires}
    assert req["frontend-proxy"]["critical"] is True
    assert req["checkout"]["share"] == 0.5


def test_match_journey_root_is_exact():
    js = [{"id": "browse", "routes": ["/"]}, {"id": "view", "routes": ["/product/"]}]
    assert match_journey("/", js) == "browse"
    assert match_journey("/product/123", js) == "view"
    assert match_journey("/other", js) is None


def test_agent_run_counts_tools():
    st = run([
        sp("t", "1", "", "agent", SERVER, name="astronomy_shop_agent_workflow"),
        sp("t", "2", "1", "agent", INTERNAL, name="execute_tool search"),
        sp("t", "3", "1", "agent", INTERNAL, **{"gen_ai.operation.name": "execute_tool"}),
        sp("t", "4", "1", "agent", CLIENT, dur=900, **{"gen_ai.operation.name": "chat"}),
    ])
    props = st.agent_props[0]["props"]
    assert props["tool_calls_per_run"] == 2 and props["llm_p95_ms"] == 900


def test_window_waits_for_finalise_lag_and_prunes():
    w = SpanWindow(IngestConfig(window_ms=60_000, finalise_lag_ms=10_000))
    w.add([sp("t", "1", "", "frontend", SERVER, t=100_000)])
    assert w.aggregate(105_000).services == []  # too fresh
    assert w.aggregate(115_000).services[0]["id"] == "frontend"
    w.aggregate(500_000)
    assert not w.traces


def test_parse_otlp_json_with_string_enums_and_offset():
    doc = {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "cart"}}]},
                              "scopeSpans": [{"spans": [{
                                  "traceId": "ab", "spanId": "cd", "name": "GetCart", "kind": "SPAN_KIND_SERVER",
                                  "startTimeUnixNano": "1700000000000000000", "endTimeUnixNano": "1700000000050000000",
                                  "status": {"code": "STATUS_CODE_ERROR"},
                                  "attributes": [{"key": "rpc.system", "value": {"stringValue": "grpc"}},
                                                 {"key": "n", "value": {"intValue": "3"}}]}]}]}]}
    [s] = parse_otlp_json(doc, offset_ms=5)
    assert s.service == "cart" and s.kind == SERVER and s.error
    assert s.duration_ms == 50 and s.start_ms == 1_700_000_000_000 + 5
    assert s.attrs["n"] == 3


def test_unanswered_call_named_via_rpc_method_new_semconv():
    # real demo (Oct 2026): checkout's gRPC client spans carry rpc.method + rpc.system.name, no rpc.service
    st = run([
        sp("t", "1", "", "checkout", SERVER, err=True),
        sp("t", "2", "1", "checkout", CLIENT, err=True, **{"rpc.method": "oteldemo.PaymentService/Charge",
                                                              "rpc.system.name": "grpc",
                                                              "server.address": "badAddress"}),
    ])
    calls = {(c["src"], c["dst"]): c for c in st.calls}
    assert calls[("checkout", "payment")]["protocol"] == "grpc"
    assert calls[("checkout", "payment")]["unanswered_rate"] > 0


def test_journey_entry_span_under_load_generator_parent():
    cfg = IngestConfig(window_ms=60_000, finalise_lag_ms=0, journeys=CFG.journeys,
                       non_candidates=frozenset({"load-generator"}))
    st = run([
        sp("t", "0", "", "load-generator", CLIENT),
        sp("t", "1", "0", "frontend-proxy", SERVER, **{"http.url": "http://frontend-proxy:8080/api/checkout"}),
        sp("t", "2", "1", "frontend-proxy", CLIENT),
        sp("t", "3", "2", "frontend", SERVER, **{"http.route": "/api/checkout"}),
    ], cfg)
    j = {x["id"]: x for x in st.journeys}
    assert j["journey:checkout"]["rps"] > 0  # counted once, at the proxy
    assert abs(j["journey:checkout"]["rps"] - 1 / 60) < 1e-9
    assert all(r["svc"] != "load-generator" for r in st.requires)


def test_flag_evaluation_events_become_affects_rows():
    doc = {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "cart"}}]},
                              "scopeSpans": [{"spans": [{
                                  "traceId": "t", "spanId": "1", "name": "op", "kind": 2,
                                  "startTimeUnixNano": "1000000000", "endTimeUnixNano": "1001000000",
                                  "events": [{"name": "feature_flag.evaluation", "attributes": [
                                      {"key": "feature_flag.key", "value": {"stringValue": "cartFailure"}}]}]}]}]}]}
    spans = parse_otlp_json(doc)
    assert spans[0].flag_keys == ("cartFailure",)
    st = run(spans)
    assert st.flag_affects == [{"flag": "cartFailure", "svc": "cart"}]


def test_4xx_with_failing_handler_counts_as_failure():
    # demo frontend: failed checkout -> HTTP 422 on the server span, exception on an inner span
    st = run([
        sp("t", "1", "", "frontend", SERVER, **{"http.route": "/api/checkout", "http.status_code": "422"}),
        sp("t", "2", "1", "frontend", INTERNAL, err=True),
        sp("t", "3", "", "frontend", SERVER, **{"http.route": "/api/checkout", "http.status_code": "404"}),
        sp("t", "4", "", "frontend", SERVER, **{"http.route": "/api/cart"}),
        sp("t", "5", "", "frontend", SERVER, **{"http.route": "/api/cart"}),
    ])
    f = {x["id"]: x for x in st.services}["frontend"]
    assert f["err_rate"] == 0.25         # 1 of 4 server spans: only the 422 with a failing handler
    assert f["op_err_rate"] == 0.5       # /api/checkout: 1 of 2


def test_slowest_route_p95():
    spans = [sp("t", str(i), "", "shipping", SERVER, dur=2, **{"http.route": "/get-quote"}) for i in range(20)]
    spans += [sp("t", f"s{i}", "", "shipping", SERVER, dur=3, **{"http.route": "/ship-order"}) for i in range(9)]
    spans += [sp("t", "slow", "", "shipping", SERVER, dur=5000, **{"http.route": "/ship-order"})]
    st = run(spans)
    shipping = {x["id"]: x for x in st.services}["shipping"]
    assert shipping["p95_ms"] < 10 and shipping["op_p95_ms"] == 5000


def test_consumer_spans_are_inbound_work():
    # a throttled Kafka consumer (3 s per record) must look like a slow service
    spans = [sp("t", f"c{i}", "", "fraud-detection", CONSUMER, dur=3000, name="process orders",
                **{"messaging.system": "kafka", "messaging.destination.name": "orders"}) for i in range(6)]
    f = {x["id"]: x for x in run(spans).services}["fraud-detection"]
    assert f["rps"] > 0 and f["p95_ms"] == 3000 and f["server_spans"] == 6
