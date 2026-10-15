// purpose: Snapshot the incident a chaos run PRODUCED into the eval graph
// algorithm: -
MATCH (r:ChaosRun {id: $run})
MERGE (i:Incident {id: $incident_id})
SET i.status = 'snapshot', i.root_target = $verdict
MERGE (r)-[:PRODUCED]->(i)
