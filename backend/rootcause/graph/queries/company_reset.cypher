// purpose: Company setup: forget edited teams, people and runbooks, and journeys not in $keep (before re-seeding)
// algorithm: -
MATCH (n)
WHERE n:Team OR n:Person OR n:Runbook
DETACH DELETE n
;
MATCH (j:Journey)
WHERE NOT j.id IN $keep
DETACH DELETE j
