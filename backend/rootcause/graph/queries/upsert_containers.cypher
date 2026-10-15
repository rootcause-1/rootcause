// purpose: Write container CPU/memory samples and the Service-RUNS_IN->Container link (copied onto the service for alerting)
// algorithm: -
UNWIND $rows AS r
MERGE (c:Container {id: r.container})
SET c.cpu_pct = r.cpu_pct, c.mem_mb = r.mem_mb, c.mem_slope = r.mem_slope, c.last_seen = $now
WITH c, r
WHERE r.service IS NOT NULL
MERGE (s:Service {id: r.service})
MERGE (s)-[:RUNS_IN]->(c)
SET s.cpu_pct = r.cpu_pct, s.mem_mb = r.mem_mb, s.mem_slope = r.mem_slope
