// purpose: Everything upstream of a node (who calls it, transitively) via CALLED_BY: blast radius and prediction
// algorithm: algo.bfs
MATCH (x {id: $id})
CALL algo.bfs(x, $depth, 'CALLED_BY') YIELD nodes, edges
RETURN [n IN nodes | n.id] AS upstream
