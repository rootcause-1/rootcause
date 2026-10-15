// purpose: Resolved incidents with their signal fingerprint, fixes and similar incidents (Memory tab)
// algorithm: -
MATCH (i:Incident)
WHERE i.status = 'resolved'
OPTIONAL MATCH (i)-[:HAS_SIGNAL]->(sp:SignalPattern)
WITH i, collect(DISTINCT sp.id) AS signals
OPTIONAL MATCH (i)-[:RESOLVED_BY]->(a:Action)
WITH i, signals, collect(DISTINCT a.kind + ':' + a.target) AS fixes
OPTIONAL MATCH (i)-[s:SIMILAR_TO]->(p:Incident)
RETURN i.id AS id, i.root_target AS root, i.ttr_ms AS ttr_ms, i.resolved_ts AS resolved_ts, signals, fixes,
       collect(DISTINCT p.id) AS similar
ORDER BY resolved_ts DESC
LIMIT 50
