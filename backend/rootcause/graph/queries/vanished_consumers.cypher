// purpose: Invisible fault: consumers of an anomalous queue whose CONSUMED_BY edge stopped being refreshed (no consumer spans)
// algorithm: -
MATCH (qu:Queue)-[c:CONSUMED_BY]->(s:Service)
WHERE qu.id IN $members AND c.last_seen < $stale_before
RETURN qu.id AS queue, s.id AS consumer, c.last_seen AS last_seen
