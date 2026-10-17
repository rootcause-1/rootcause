// purpose: Codebase: where each known feature flag is READ_IN the code (file and line)
// algorithm: -
UNWIND $reads AS r
MATCH (m:CodeModule {id: 'code:' + r.module})
MATCH (f:FeatureFlag {id: r.flag})
MERGE (f)-[e:READ_IN {file: r.file}]->(m)
SET e.line = r.line
