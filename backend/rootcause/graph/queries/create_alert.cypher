// purpose: Create a firing Alert FIRED_ON a node, mark the node :Anomalous and merge its SignalPattern
// algorithm: -
MATCH (n {id: $target})
WHERE n:Service OR n:Queue OR n:Datastore
CREATE (a:Alert {id: $id, kind: $kind, target: $target, value: $value, threshold: $threshold,
                 baseline: $baseline, dev: $dev, ts: $ts, status: 'firing'})
CREATE (a)-[:FIRED_ON]->(n)
SET n:Anomalous
MERGE (sp:SignalPattern {id: $signal})
RETURN a.id AS id
