// purpose: Codebase: the code behind a node (module, language, flag reads, latest commits, gRPC services, repo)
// algorithm: -
MATCH (m:CodeModule)-[:IMPLEMENTS]->(s {id: $node_id})
OPTIONAL MATCH (f:FeatureFlag)-[r:READ_IN]->(m)
WITH m, collect(DISTINCT {flag: f.id, file: r.file, line: r.line}) AS reads
OPTIONAL MATCH (k:Commit)-[:TOUCHED]->(m)
WITH m, reads, k
ORDER BY k.ts DESC
WITH m, reads, collect({sha: k.id, ts: k.ts, subject: k.subject}) AS commits
OPTIONAL MATCH (m)-[:SERVES]->(x:RpcService)
WITH m, reads, commits, collect(x.name) AS rpc
OPTIONAL MATCH (repo:Repo)-[:CONTAINS]->(m)
RETURN m.id AS id, m.name AS module, m.path AS path, m.language AS language, m.files AS files, m.loc AS loc,
       m.owners AS owners, reads, commits[0..3] AS commits, rpc, repo.url AS repo, repo.sha AS sha
