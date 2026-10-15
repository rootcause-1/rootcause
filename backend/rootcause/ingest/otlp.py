"""OTLP/HTTP trace parsing: JSON (preferred) or protobuf body -> list of flat `Span` records.

Uses no graph queries. The FastAPI route `POST /v1/traces` (api/main.py) calls `parse_body` and hands the spans
to the pipeline, which buffers them in the 60 s span window (ingest/spans.py).
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from typing import Any

SERVER, CLIENT, PRODUCER, CONSUMER, INTERNAL = 2, 3, 4, 5, 1
_KIND_NAMES = {
    "SPAN_KIND_INTERNAL": INTERNAL, "SPAN_KIND_SERVER": SERVER, "SPAN_KIND_CLIENT": CLIENT,
    "SPAN_KIND_PRODUCER": PRODUCER, "SPAN_KIND_CONSUMER": CONSUMER,
}
STATUS_ERROR = 2


@dataclass(slots=True)
class Span:
    trace_id: str
    span_id: str
    parent_id: str
    service: str
    name: str
    kind: int
    start_ms: int
    end_ms: int
    error: bool
    attrs: dict[str, Any] = field(default_factory=dict)
    flag_keys: tuple[str, ...] = ()  # feature flags evaluated in this span (feature_flag.evaluation events)

    @property
    def duration_ms(self) -> float:
        return float(max(0, self.end_ms - self.start_ms))


def _any_value(v: dict[str, Any]) -> Any:
    """Decode an OTLP AnyValue ({"stringValue": "x"} etc.)."""
    if not isinstance(v, dict):
        return v
    for key in ("stringValue", "boolValue", "doubleValue"):
        if key in v:
            return v[key]
    if "intValue" in v:
        return int(v["intValue"])
    if "arrayValue" in v:
        return [_any_value(x) for x in v["arrayValue"].get("values", [])]
    if "kvlistValue" in v:
        return {kv["key"]: _any_value(kv.get("value", {})) for kv in v["kvlistValue"].get("values", [])}
    return None


def _attrs(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {kv["key"]: _any_value(kv.get("value", {})) for kv in items or []}


def _kind(k: Any) -> int:
    if isinstance(k, int):
        return k
    if isinstance(k, str):
        return _KIND_NAMES.get(k, int(k) if k.isdigit() else INTERNAL)
    return INTERNAL


def _status_error(status: dict[str, Any] | None) -> bool:
    code = (status or {}).get("code", 0)
    return code == STATUS_ERROR or code == "STATUS_CODE_ERROR"


def _flag_keys(sp: dict[str, Any]) -> tuple[str, ...]:
    """OpenFeature's OTel hook records each evaluation as a span event carrying `feature_flag.key`."""
    keys = []
    for ev in sp.get("events") or []:
        for kv in ev.get("attributes") or []:
            if kv.get("key") == "feature_flag.key":
                keys.append(str(_any_value(kv.get("value", {}))))
    return tuple(keys)


def parse_otlp_json(doc: dict[str, Any], offset_ms: int = 0) -> list[Span]:
    """Parse an ExportTraceServiceRequest in OTLP JSON. `offset_ms` time-shifts spans (replay)."""
    out: list[Span] = []
    for rs in doc.get("resourceSpans", []) or []:
        res_attrs = _attrs((rs.get("resource") or {}).get("attributes"))
        service = str(res_attrs.get("service.name", "unknown"))
        for ss in rs.get("scopeSpans", []) or rs.get("instrumentationLibrarySpans", []) or []:
            for sp in ss.get("spans", []) or []:
                out.append(Span(
                    trace_id=str(sp.get("traceId", "")),
                    span_id=str(sp.get("spanId", "")),
                    parent_id=str(sp.get("parentSpanId") or ""),
                    service=service,
                    name=str(sp.get("name", "")),
                    kind=_kind(sp.get("kind", INTERNAL)),
                    start_ms=int(sp.get("startTimeUnixNano", 0)) // 1_000_000 + offset_ms,
                    end_ms=int(sp.get("endTimeUnixNano", 0)) // 1_000_000 + offset_ms,
                    error=_status_error(sp.get("status")),
                    attrs=_attrs(sp.get("attributes")),
                    flag_keys=_flag_keys(sp),
                ))
    return out


def protobuf_to_json(body: bytes) -> dict[str, Any]:
    """Fallback if the collector cannot send JSON: decode protobuf into the same JSON shape.

    MessageToDict renders ids as base64 instead of hex; that is fine because ids are only compared to each other.
    """
    from google.protobuf.json_format import MessageToDict
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    req = ExportTraceServiceRequest()
    req.ParseFromString(body)
    return MessageToDict(req)


def parse_body(body: bytes, content_type: str, content_encoding: str = "") -> dict[str, Any]:
    """Return the OTLP JSON document for a request body (JSON or protobuf, optionally gzip-compressed:
    the collector's otlp_http exporter gzips by default)."""
    if "gzip" in (content_encoding or "") or body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    if "protobuf" in (content_type or ""):
        return protobuf_to_json(body)
    return json.loads(body or b"{}")
