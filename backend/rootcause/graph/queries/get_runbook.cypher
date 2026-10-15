// purpose: Runbooks FOR a node and the signal patterns they REMEDIATE
// algorithm: -
MATCH (rb:Runbook)-[:FOR]->(s {id: $node_id})
OPTIONAL MATCH (rb)-[:REMEDIATES]->(sp:SignalPattern)
RETURN rb.id AS id, rb.title AS title, rb.url AS url, rb.steps AS steps, collect(sp.id) AS remediates
