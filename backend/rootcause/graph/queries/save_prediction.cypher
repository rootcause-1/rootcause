// purpose: Save a what-if Prediction and its PREDICTS edges to services, queues and journeys
// algorithm: -
CREATE (p:Prediction {id: $id, source: $source, ts: $now, services: $services, queues: $queues, journeys: $journeys})
;
MATCH (p:Prediction {id: $id})
UNWIND $targets AS tid
MATCH (x {id: tid})
WHERE x:Service OR x:Queue OR x:Journey
CREATE (p)-[:PREDICTS]->(x)
