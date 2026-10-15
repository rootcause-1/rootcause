// purpose: Container changes (restarts) that hit a service via Service-RUNS_IN->Container shortly before onset
// algorithm: -
MATCH (c:Change)-[:CHANGED]->(k:Container)<-[:RUNS_IN]-(s)
WHERE s.id = $node_id AND c.ts >= $onset - $window_ms AND c.ts <= $onset + 30000
RETURN c.id AS change, k.id AS container, c.kind AS kind, c.ts AS ts, c.actor AS actor
ORDER BY c.ts DESC
