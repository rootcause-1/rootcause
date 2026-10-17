// purpose: Company setup: delete a team (with its people), a journey or a runbook
// algorithm: -
MATCH (p:Person)-[:MEMBER_OF]->(:Team {id: $id})
DETACH DELETE p
;
MATCH (n)
WHERE n.id = $id AND (n:Team OR n:Journey OR n:Runbook)
DETACH DELETE n
