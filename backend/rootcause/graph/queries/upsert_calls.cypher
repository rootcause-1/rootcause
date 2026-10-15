// purpose: Write CALLS edges and their CALLED_BY mirrors (kept in sync) from paired client/server spans
// algorithm: -
UNWIND $rows AS r
MERGE (a:Service {id: r.src})
MERGE (b:Service {id: r.dst})
MERGE (a)-[c:CALLS]->(b)
SET c.protocol = r.protocol, c.rps = r.rps, c.err_rate = r.err_rate, c.p95_ms = r.p95_ms,
    c.unanswered_rate = r.unanswered_rate, c.last_seen = $now
MERGE (b)-[cb:CALLED_BY]->(a)
SET cb.protocol = r.protocol, cb.rps = r.rps, cb.err_rate = r.err_rate, cb.last_seen = $now
