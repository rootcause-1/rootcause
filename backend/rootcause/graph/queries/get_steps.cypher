// purpose: The investigation trail of an incident in order, with cited node ids
// algorithm: -
MATCH (i:Incident {id: $id})-[:INVESTIGATED_BY]->(s:Step)
OPTIONAL MATCH (s)-[:CITED]->(x)
RETURN s.id AS id, s.n AS n, s.tool AS tool, s.args AS args, s.summary AS summary, s.ts AS ts, collect(x.id) AS cited
ORDER BY n
