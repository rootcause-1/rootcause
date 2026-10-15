// purpose: UI snapshot: services, queues and datastores that take part in traffic (or are anomalous), with live metrics
// algorithm: -
MATCH (n)
WHERE (n:Service OR n:Queue OR n:Datastore)
  AND (n:Anomalous OR (n)-[:CALLS|CALLED_BY|USES|PRODUCES_TO|CONSUMED_BY]-())
RETURN n.id AS id, labels(n) AS labels, n.rps AS rps, n.err_rate AS err_rate, n.p95_ms AS p95_ms,
       n.self_err_rate AS self_err_rate, n.cpu_pct AS cpu_pct, n.mem_mb AS mem_mb, n.lag AS lag
