// purpose: Record a feature-flag Change (from -> to) and link it to the FeatureFlag it CHANGED
// algorithm: -
MERGE (f:FeatureFlag {id: $flag})
SET f.variant = $to
CREATE (c:Change {id: $id, kind: 'flag', from_variant: $from_variant, to: $to, ts: $ts, actor: $actor})
CREATE (c)-[:CHANGED]->(f)
RETURN c.id AS id
