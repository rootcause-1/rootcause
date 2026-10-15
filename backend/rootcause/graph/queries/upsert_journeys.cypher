// purpose: Write journey success rates and the REQUIRES {share, critical} edges to services seen in their traces
// algorithm: -
UNWIND $journeys AS r
MERGE (j:Journey {id: r.id})
SET j.success_rate = r.success_rate, j.rps = r.rps, j.last_seen = $now
;
UNWIND $requires AS r
MATCH (j:Journey {id: r.journey})
MERGE (s:Service {id: r.svc})
MERGE (j)-[q:REQUIRES]->(s)
SET q.share = r.share, q.critical = r.critical, q.last_seen = $now
