// purpose: Flag changes that hit a node (via FeatureFlag-AFFECTS->node) shortly before an incident's onset
// algorithm: -
MATCH (c:Change)-[:CHANGED]->(f:FeatureFlag)-[:AFFECTS]->(s)
WHERE s.id = $node_id AND c.ts >= $onset - $window_ms AND c.ts <= $onset + 30000
RETURN c.id AS change, f.id AS flag, c.from_variant AS from_variant, c.to AS to, c.ts AS ts, c.actor AS actor
ORDER BY c.ts DESC
