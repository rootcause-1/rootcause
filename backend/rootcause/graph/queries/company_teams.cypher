// purpose: Company setup: every team, the services it OWNS and its people (MEMBER_OF, on call)
// algorithm: -
MATCH (t:Team)
OPTIONAL MATCH (t)-[:OWNS]->(s)
WITH t, collect(DISTINCT s.id) AS owns
OPTIONAL MATCH (p:Person)-[:MEMBER_OF]->(t)
RETURN t.id AS id, t.name AS name, owns,
       collect({id: p.id, name: p.name, on_call: p.on_call, contact: p.contact}) AS people
ORDER BY id
