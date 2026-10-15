// purpose: Flat alert table for an incident (input to the chaos baselines: loudest, first, highest-error, LLM-no-graph)
// algorithm: -
MATCH (a:Alert)-[:PART_OF]->(i:Incident {id: $id})
MATCH (a)-[:FIRED_ON]->(n)
RETURN a.target AS target, a.kind AS kind, a.ts AS ts, a.value AS value,
       n.err_rate AS err_rate, n.rps AS rps, n.p95_ms AS p95_ms, n.self_err_rate AS self_err_rate
