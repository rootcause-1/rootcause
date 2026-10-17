// purpose: Codebase: the latest commits (sha, time, subject) that TOUCHED each module
// algorithm: -
UNWIND $commits AS c
MATCH (m:CodeModule {id: 'code:' + c.module})
MERGE (k:Commit {id: c.sha})
SET k.ts = c.ts, k.subject = c.subject
MERGE (k)-[:TOUCHED]->(m)
