// purpose: Resolve an incident (status, time to resolve) and link the Action it was RESOLVED_BY
// algorithm: -
MATCH (i:Incident {id: $id})
SET i.status = 'resolved', i.resolved_ts = $now, i.ttr_ms = $now - i.created_ts, i.resolution = $resolution
;
MATCH (i:Incident {id: $id}), (a:Action {id: $action})
MERGE (i)-[:RESOLVED_BY]->(a)
