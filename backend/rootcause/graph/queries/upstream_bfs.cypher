// purpose: Everything upstream of a node (who calls it, transitively) via CALLED_BY: blast radius and prediction.
// $exclude drops non-candidates (load generator, browser) from the result.
// algorithm: algo.bfs
MATCH (x {id: $id})
CALL algo.bfs(x, $depth, 'CALLED_BY') YIELD nodes, edges
RETURN [n IN nodes WHERE NOT n.id IN $exclude | n.id] AS upstream
