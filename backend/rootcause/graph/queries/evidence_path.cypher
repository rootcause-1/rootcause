// purpose: Shortest BLAMES path from the incident entry point to the root cause (the evidence chain)
// algorithm: shortestPath (FalkorDB only allows shortestPath inside WITH/RETURN, not in MATCH)
MATCH (a {id: $from}), (b {id: $to})
WITH shortestPath((a)-[:BLAMES*1..8]->(b)) AS p
WHERE p IS NOT NULL
RETURN [n IN nodes(p) | n.id] AS path
