// purpose: Past resolved incidents ranked by Jaccard similarity of their SignalPatterns, with their fixes and root cause
// algorithm: Jaccard over HAS_SIGNAL
MATCH (cur:Incident {id: $id})-[:HAS_SIGNAL]->(sp:SignalPattern)<-[:HAS_SIGNAL]-(past:Incident)
WHERE past.status = 'resolved' AND past.id <> cur.id
WITH cur, past, count(sp) AS shared
MATCH (cur)-[:HAS_SIGNAL]->(a)
WITH cur, past, shared, count(a) AS ca
MATCH (past)-[:HAS_SIGNAL]->(b)
WITH past, shared, ca, count(b) AS cb
OPTIONAL MATCH (past)-[:RESOLVED_BY]->(act:Action)
RETURN past.id AS incident, toFloat(shared) / (ca + cb - shared) AS jaccard,
       collect(act.kind + ':' + act.target) AS fixes, past.root_target AS root
ORDER BY jaccard DESC LIMIT 3
