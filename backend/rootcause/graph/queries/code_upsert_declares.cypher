// purpose: Codebase: dependencies the repo declares between modules (compose depends_on, *_ADDR env vars)
// algorithm: -
UNWIND $declares AS d
MATCH (a:CodeModule {id: 'code:' + d.src}), (b:CodeModule {id: 'code:' + d.dst})
MERGE (a)-[r:DECLARES]->(b)
SET r.via = d.via
