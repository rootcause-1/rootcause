// purpose: Company setup: drop a runbook's FOR / REMEDIATES edges before seed_runbooks writes the edited runbook again
// algorithm: -
MATCH (rb:Runbook {id: $id})-[r:FOR|REMEDIATES]->()
DELETE r
