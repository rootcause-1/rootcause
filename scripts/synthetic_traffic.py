"""DEV SMOKE TEST ONLY: synthetic OTLP JSON traffic so RootCause can be exercised without the 6 GB demo.

Never use it for recordings, replay scenarios, the chaos scorecard or the demo video (CLAUDE.md rule 7).
It sends a tiny topology (frontend-proxy -> frontend -> checkout -> payment, frontend -> product-catalog) once a
second to the API's OTLP port. Control it with files:
  echo fail > /tmp/rc/phase        # payment errors (like paymentFailure)
  touch /tmp/rc/unreach            # with phase=fail: payment server spans vanish (like paymentUnreachable)
  echo ok > /tmp/rc/phase          # healthy
Set `detect.learn_seconds` low in a copied config dir (RC_CONFIG_DIR) to skip the 3 min baseline.
"""

import json
import os
import random
import time
import urllib.request

URL = os.environ.get("RC_OTLP_URL", "http://127.0.0.1:4318/v1/traces")


def hexid(n):
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def span(svc, name, kind, tid, sid, pid, s, e, err, attrs=None):
    return svc, {
        "traceId": tid,
        "spanId": sid,
        "parentSpanId": pid,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(s * 1_000_000),
        "endTimeUnixNano": str(e * 1_000_000),
        "status": {"code": 2 if err else 0},
        "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in (attrs or {}).items()],
    }


def checkout_trace(fail):
    t = int(time.time() * 1000)
    tid = hexid(32)
    out = []
    ids = [hexid(16) for _ in range(7)]
    out.append(
        span(
            "frontend-proxy", "ingress", 2, tid, ids[0], "", t, t + 60, fail, {"http.route": "/api/checkout"}
        )
    )
    out.append(span("frontend-proxy", "router frontend", 3, tid, ids[1], ids[0], t + 1, t + 59, fail))
    out.append(
        span(
            "frontend",
            "POST /api/checkout",
            2,
            tid,
            ids[2],
            ids[1],
            t + 2,
            t + 58,
            fail,
            {"http.route": "/api/checkout"},
        )
    )
    out.append(
        span(
            "frontend",
            "oteldemo.CheckoutService/PlaceOrder",
            3,
            tid,
            ids[3],
            ids[2],
            t + 3,
            t + 57,
            fail,
            {"rpc.service": "oteldemo.CheckoutService"},
        )
    )
    out.append(
        span("checkout", "oteldemo.CheckoutService/PlaceOrder", 2, tid, ids[4], ids[3], t + 4, t + 56, fail)
    )
    out.append(
        span(
            "checkout",
            "oteldemo.PaymentService/Charge",
            3,
            tid,
            ids[5],
            ids[4],
            t + 5,
            t + 30,
            fail,
            {"rpc.service": "oteldemo.PaymentService"},
        )
    )
    if os.path.exists("/tmp/rc/unreach") and fail:
        return out
    out.append(span("payment", "oteldemo.PaymentService/Charge", 2, tid, ids[6], ids[5], t + 6, t + 29, fail))
    return out


def browse_trace():
    t = int(time.time() * 1000)
    tid = hexid(32)
    ids = [hexid(16) for _ in range(5)]
    return [
        span(
            "frontend-proxy", "ingress", 2, tid, ids[0], "", t, t + 40, False, {"http.route": "/api/products"}
        ),
        span("frontend-proxy", "router frontend", 3, tid, ids[1], ids[0], t + 1, t + 39, False),
        span(
            "frontend",
            "GET /api/products",
            2,
            tid,
            ids[2],
            ids[1],
            t + 2,
            t + 38,
            False,
            {"http.route": "/api/products"},
        ),
        span(
            "frontend",
            "oteldemo.ProductCatalogService/ListProducts",
            3,
            tid,
            ids[3],
            ids[2],
            t + 3,
            t + 20,
            False,
            {"rpc.service": "oteldemo.ProductCatalogService"},
        ),
        span(
            "product-catalog",
            "oteldemo.ProductCatalogService/ListProducts",
            2,
            tid,
            ids[4],
            ids[3],
            t + 4,
            t + 19,
            False,
        ),
    ]


while True:
    phase = open("/tmp/rc/phase").read().strip() if os.path.exists("/tmp/rc/phase") else "ok"
    spans = []
    for _ in range(10):
        spans += checkout_trace(phase == "fail") + browse_trace()
    by = {}
    for svc, s in spans:
        by.setdefault(svc, []).append(s)
    body = {
        "resourceSpans": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": svc}}]},
                "scopeSpans": [{"spans": ss}],
            }
            for svc, ss in by.items()
        ]
    }
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print("send failed", e)
    time.sleep(1)
