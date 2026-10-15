// purpose: UI snapshot: CALLS, USES, PRODUCES_TO, CONSUMED_BY and BLAMES edges with live metrics
// algorithm: -
MATCH (a)-[r]->(b)
WHERE type(r) IN ['CALLS', 'USES', 'PRODUCES_TO', 'CONSUMED_BY', 'BLAMES']
RETURN a.id AS source, b.id AS target, type(r) AS type, r.rps AS rps, r.err_rate AS err_rate, r.p95_ms AS p95_ms,
       r.rate AS rate, r.weight AS weight, r.protocol AS protocol
