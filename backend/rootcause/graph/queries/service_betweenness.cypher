// purpose: Betweenness centrality of services in the CALLS graph (restart risk: how much traffic flows through it)
// algorithm: algo.betweenness
CALL algo.betweenness({nodeLabels: ['Service'], relationshipTypes: ['CALLS'], samplingSize: 64, samplingSeed: 42})
YIELD node, score
RETURN node.id AS id, score
