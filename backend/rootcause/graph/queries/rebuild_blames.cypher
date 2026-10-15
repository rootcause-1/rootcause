// purpose: Rebuild the transient BLAMES subgraph between :Anomalous nodes (sync calls blame the callee, a lagging queue blames its consumer)
// algorithm: -
MATCH ()-[b:BLAMES]->() DELETE b
;
MATCH (a:Anomalous)-[r:CALLS|USES]->(b:Anomalous)
CREATE (a)-[:BLAMES {weight: coalesce(r.err_rate, 0.0) + 0.01}]->(b)
;
MATCH (q:Queue:Anomalous)-[:CONSUMED_BY]->(c:Anomalous)
CREATE (q)-[:BLAMES {weight: 1.0}]->(c)
