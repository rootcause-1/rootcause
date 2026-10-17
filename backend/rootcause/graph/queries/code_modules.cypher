// purpose: Codebase tab: every scanned module with what it implements, declares, the flags it reads and its last commit
// algorithm: -
MATCH (r:Repo)-[:CONTAINS]->(m:CodeModule)
OPTIONAL MATCH (m)-[:IMPLEMENTS]->(s)
WITH r, m, collect(DISTINCT s.id) AS implements
OPTIONAL MATCH (f:FeatureFlag)-[:READ_IN]->(m)
WITH r, m, implements, collect(DISTINCT f.id) AS flags
OPTIONAL MATCH (m)-[:DECLARES]->(d:CodeModule)
WITH r, m, implements, flags, collect(DISTINCT d.name) AS declares
OPTIONAL MATCH (k:Commit)-[:TOUCHED]->(m)
RETURN r.url AS repo, r.sha AS sha, r.scanned_ts AS scanned_ts, m.name AS name, m.path AS path,
       m.language AS language, m.files AS files, m.loc AS loc, m.kind AS kind, implements, flags, declares,
       max(k.ts) AS last_commit_ts
ORDER BY name
