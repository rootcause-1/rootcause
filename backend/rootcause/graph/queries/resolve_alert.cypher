// purpose: Resolve an alert and remove :Anomalous from its node when no firing alert remains on it
// algorithm: -
MATCH (a:Alert {id: $id})
SET a.status = 'resolved', a.resolved_ts = $ts
;
MATCH (n {id: $target})
OPTIONAL MATCH (other:Alert)-[:FIRED_ON]->(n)
WHERE other.status = 'firing'
WITH n, count(other) AS still
WHERE still = 0
REMOVE n:Anomalous
