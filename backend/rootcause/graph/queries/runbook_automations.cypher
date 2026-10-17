// purpose: Runbooks FOR a node that define an automation hook (a URL RootCause may call after human approval)
// algorithm: -
MATCH (rb:Runbook)-[:FOR]->(s {id: $node_id})
WHERE rb.automation_url IS NOT NULL AND rb.automation_url <> ''
RETURN rb.id AS id, rb.title AS title, rb.automation_url AS url, coalesce(rb.automation_risk, 'medium') AS risk
