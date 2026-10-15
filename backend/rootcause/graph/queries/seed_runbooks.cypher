// purpose: Seed runbooks, the service each is FOR and the signal patterns each REMEDIATES
// algorithm: -
UNWIND $runbooks AS r
MERGE (rb:Runbook {id: r.id})
SET rb.title = r.title, rb.url = r.url, rb.steps = r.steps
MERGE (s:Service {id: r.service})
MERGE (rb)-[:FOR]->(s)
WITH rb, r
UNWIND r.remediates AS sig
MERGE (sp:SignalPattern {id: sig})
MERGE (rb)-[:REMEDIATES]->(sp)
