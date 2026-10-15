// purpose: Shortest BLAMES path from the incident entry point to the root cause (the evidence chain)
// algorithm: shortestPath
MATCH (a {id: $from}), (b {id: $to})
WITH a, b
MATCH p = shortestPath((a)-[:BLAMES*1..8]->(b))
RETURN [n IN nodes(p) | n.id] AS path
