// purpose: Company setup: runbooks, the service each is FOR, what it REMEDIATES and its optional automation hook
// algorithm: -
MATCH (rb:Runbook)
OPTIONAL MATCH (rb)-[:FOR]->(s)
OPTIONAL MATCH (rb)-[:REMEDIATES]->(sp:SignalPattern)
RETURN rb.id AS id, s.id AS service, rb.title AS title, rb.url AS url, rb.steps AS steps,
       collect(sp.id) AS remediates, rb.automation_url AS automation_url, rb.automation_risk AS automation_risk
ORDER BY id
