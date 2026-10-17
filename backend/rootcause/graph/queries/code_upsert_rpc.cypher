// purpose: Codebase: gRPC services and methods from .proto files, linked to the module that SERVES them
// algorithm: -
UNWIND $rpc AS x
MERGE (s:RpcService {id: x.id})
SET s.name = x.name, s.methods = x.methods, s.file = x.file
WITH s, x
WHERE x.module IS NOT NULL
MATCH (m:CodeModule {id: 'code:' + x.module})
MERGE (m)-[:SERVES]->(s)
