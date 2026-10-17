// purpose: Company setup: drop a team's OWNS edges and its people before seed_org writes the edited team again
// algorithm: -
MATCH (t:Team {id: $id})-[o:OWNS]->()
DELETE o
;
MATCH (p:Person)-[:MEMBER_OF]->(:Team {id: $id})
DETACH DELETE p
