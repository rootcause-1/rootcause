// purpose: Codebase: forget the previous scan (repo, code modules, gRPC services, commits) before writing a new one
// algorithm: -
MATCH (n)
WHERE n:Repo OR n:CodeModule OR n:RpcService OR n:Commit
DETACH DELETE n
