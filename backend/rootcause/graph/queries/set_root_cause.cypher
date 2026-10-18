// purpose: Point an incident's ROOT_CAUSE at the top hypothesis node (edge causes keep the edge name on the relationship)
// algorithm: -
MATCH (i:Incident {id: $id})-[r:ROOT_CAUSE]->()
DELETE r
;
MATCH (i:Incident {id: $id}), (n {id: $node})
WHERE n:Service OR n:Queue OR n:Datastore  // a Container can share the service's id
CREATE (i)-[:ROOT_CAUSE {edge: $edge, score: $score}]->(n)
SET i.root_target = $target, i.confidence = $score
