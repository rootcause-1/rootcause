// purpose: Seed (or save) runbooks, the service each is FOR, the signal patterns each REMEDIATES and the automation hook
// algorithm: -
UNWIND $runbooks AS r
MERGE (rb:Runbook {id: r.id})
SET rb.title = r.title, rb.url = r.url, rb.steps = r.steps,
    rb.automation_url = r.automation_url, rb.automation_risk = r.automation_risk
MERGE (s:Service {id: r.service})
MERGE (rb)-[:FOR]->(s)
WITH rb, r
UNWIND r.remediates AS sig
MERGE (sp:SignalPattern {id: sig})
MERGE (rb)-[:REMEDIATES]->(sp)
