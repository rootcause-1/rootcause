// purpose: Point an incident's CAUSED_BY at the changes that hit its root cause
// algorithm: -
MATCH (i:Incident {id: $id})-[r:CAUSED_BY]->()
DELETE r
;
MATCH (i:Incident {id: $id}), (c:Change)
WHERE c.id IN $changes
CREATE (i)-[:CAUSED_BY]->(c)
