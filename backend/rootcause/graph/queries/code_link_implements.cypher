// purpose: Codebase: link each code module to the running service or datastore it IMPLEMENTS (by name)
// algorithm: -
MATCH (m:CodeModule)
MATCH (s:Service)
WHERE s.id = m.name
MERGE (m)-[:IMPLEMENTS]->(s)
;
MATCH (m:CodeModule)
MATCH (d:Datastore)
WHERE d.id ENDS WITH (':' + m.name)
MERGE (m)-[:IMPLEMENTS]->(d)
