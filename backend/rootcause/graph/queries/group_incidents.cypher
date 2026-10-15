// purpose: Group anomalous nodes into incidents = weakly connected components of the BLAMES subgraph
// algorithm: algo.WCC
CALL algo.WCC({nodeLabels: ['Anomalous'], relationshipTypes: ['BLAMES']})
YIELD node, componentId
RETURN componentId, collect(node.id) AS members
