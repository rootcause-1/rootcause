// purpose: UI snapshot: teams, the services they OWN and who is on call (the company around the services)
// algorithm: -
MATCH (t:Team)
OPTIONAL MATCH (t)-[:OWNS]->(s)
WITH t, collect(DISTINCT s.id) AS owns
OPTIONAL MATCH (p:Person)-[:MEMBER_OF]->(t)
WHERE p.on_call = true
RETURN t.id AS id, t.name AS name, owns, collect(p.name) AS on_call
