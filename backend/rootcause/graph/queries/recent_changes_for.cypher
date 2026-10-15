// purpose: Live flag changes that hit a node (via FeatureFlag-AFFECTS->node) shortly before an incident's onset.
// A change is not live if a later change to the same flag superseded it, or if it restored the variant the flag had
// while the baseline was learned (a recovery, not a cause).
// algorithm: -
MATCH (c:Change)-[:CHANGED]->(f:FeatureFlag)-[:AFFECTS]->(s)
WHERE s.id = $node_id AND c.ts >= $onset - $window_ms AND c.ts <= $onset + 30000
  AND f.variant = c.to AND c.to <> coalesce(f.baseline_variant, '')
OPTIONAL MATCH (later:Change)-[:CHANGED]->(f)
WHERE later.ts > c.ts
WITH c, f, count(later) AS newer
WHERE newer = 0
RETURN c.id AS change, f.id AS flag, c.from_variant AS from_variant, c.to AS to, c.ts AS ts, c.actor AS actor
ORDER BY c.ts DESC
