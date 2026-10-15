// purpose: Owning team of a node and its people (who is on call)
// algorithm: -
MATCH (t:Team)-[:OWNS]->(s {id: $node_id})
OPTIONAL MATCH (p:Person)-[:MEMBER_OF]->(t)
RETURN t.id AS team, t.name AS team_name,
       collect({id: p.id, name: p.name, on_call: p.on_call, contact: p.contact}) AS people
