// purpose: PageRank over BLAMES: blame flows towards the node everything points at
// algorithm: algo.pageRank
CALL algo.pageRank('Anomalous', 'BLAMES')
YIELD node, score
RETURN node.id AS id, score
