// purpose: Write per-service span metrics for the current window (rps, error rates, p95)
// algorithm: -
UNWIND $rows AS r
MERGE (s:Service {id: r.id})
SET s.rps = r.rps, s.err_rate = r.err_rate, s.op_err_rate = r.op_err_rate, s.self_err_rate = r.self_err_rate, s.p95_ms = r.p95_ms,
    s.server_spans = r.server_spans, s.last_seen = $now
