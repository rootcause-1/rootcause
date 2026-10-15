// purpose: Read CALLS edges with live metrics and baselines (for edge baselines and UI colouring)
// algorithm: -
MATCH (a:Service)-[c:CALLS]->(b:Service)
RETURN a.id AS src, b.id AS dst, c.rps AS rps, c.err_rate AS err_rate, c.p95_ms AS p95_ms,
       c.baseline_err AS baseline_err, c.baseline_p95 AS baseline_p95
