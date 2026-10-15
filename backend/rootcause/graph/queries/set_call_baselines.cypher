// purpose: Persist learned baselines (baseline_err, baseline_p95) on CALLS edges
// algorithm: -
UNWIND $rows AS r
MATCH (a:Service {id: r.src})-[c:CALLS]->(b:Service {id: r.dst})
SET c.baseline_err = r.baseline_err, c.baseline_p95 = r.baseline_p95
