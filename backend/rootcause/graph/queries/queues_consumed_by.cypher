// purpose: Queues consumed by any of the given services (prediction: a dead consumer makes its queue lag)
// algorithm: -
MATCH (qu:Queue)-[:CONSUMED_BY]->(s:Service)
WHERE s.id IN $services
RETURN DISTINCT qu.id AS queue
