// purpose: Replace an incident's IMPACTED {pct} edges to journeys
// algorithm: -
MATCH (i:Incident {id: $id})-[r:IMPACTED]->()
DELETE r
;
MATCH (i:Incident {id: $id})
UNWIND $impacts AS im
MATCH (j:Journey {id: im.journey})
CREATE (i)-[:IMPACTED {pct: im.pct}]->(j)
