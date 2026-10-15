// purpose: Save the post-incident Report and link it with HAS_REPORT
// algorithm: -
MATCH (i:Incident {id: $incident})
MERGE (r:Report {id: $id})
SET r.markdown = $markdown, r.ts = $now, r.path = $path
MERGE (i)-[:HAS_REPORT]->(r)
