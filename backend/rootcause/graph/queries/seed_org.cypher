// purpose: Seed teams, people and team ownership of services from config/seed.yaml
// algorithm: -
UNWIND $teams AS t
MERGE (team:Team {id: t.id})
SET team.name = t.name
WITH team, t
UNWIND t.owns AS sid
MERGE (s:Service {id: sid})
MERGE (team)-[:OWNS]->(s)
;
UNWIND $people AS p
MATCH (team:Team {id: p.team})
MERGE (person:Person {id: p.id})
SET person.name = p.name, person.on_call = p.on_call, person.contact = p.contact
MERGE (person)-[:MEMBER_OF]->(team)
