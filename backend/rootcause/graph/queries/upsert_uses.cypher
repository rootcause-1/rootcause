// purpose: Write USES edges to datastores/caches from db client spans, plus per-datastore aggregates
// algorithm: -
UNWIND $rows AS r
MERGE (s:Service {id: r.svc})
MERGE (d:Datastore {id: r.ds})
SET d.system = r.system
MERGE (s)-[u:USES]->(d)
SET u.rps = r.rps, u.err_rate = r.err_rate, u.p95_ms = r.p95_ms, u.last_seen = $now
;
UNWIND $stores AS r
MATCH (d:Datastore {id: r.ds})
SET d.rps = r.rps, d.err_rate = r.err_rate, d.p95_ms = r.p95_ms, d.last_seen = $now
