// purpose: Update an incident's members and link firing member alerts (PART_OF) and their SignalPatterns (HAS_SIGNAL)
// algorithm: -
MATCH (i:Incident {id: $id})
SET i.members = $members, i.quiet_ticks = $quiet, i.updated_ts = $now
;
MATCH (i:Incident {id: $id})
MATCH (a:Alert)-[:FIRED_ON]->(n)
WHERE a.status = 'firing' AND n.id IN $members
MERGE (a)-[:PART_OF]->(i)
WITH i, a
MERGE (sp:SignalPattern {id: a.target + ':' + a.kind})
MERGE (i)-[:HAS_SIGNAL]->(sp)
