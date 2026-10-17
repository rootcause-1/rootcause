// purpose: Fix it in code: the pull request RootCause opened, which incident it FIXES and which code module it CHANGES
// algorithm: -
MATCH (i:Incident {id: $incident})
MERGE (p:PullRequest {id: $url})
SET p.number = $number, p.branch = $branch, p.title = $title, p.ts = $now
MERGE (p)-[:FIXES]->(i)
WITH p
MATCH (m:CodeModule {id: $module})
MERGE (p)-[:CHANGES]->(m)
