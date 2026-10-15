// purpose: List reports, newest first
// algorithm: -
MATCH (i:Incident)-[:HAS_REPORT]->(r:Report)
RETURN r.id AS id, i.id AS incident, r.ts AS ts, r.markdown AS markdown, r.path AS path
ORDER BY ts DESC
LIMIT 50
