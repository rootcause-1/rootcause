// purpose: Replace an incident's ranked Hypothesis nodes (score + the five signal components)
// algorithm: -
MATCH (i:Incident {id: $id})-[:HAS_HYPOTHESIS]->(h:Hypothesis)
DELETE h
;
MATCH (i:Incident {id: $id})
UNWIND $hyps AS hy
CREATE (h:Hypothesis {id: hy.id, target: hy.target, score: hy.score, rank: hy.rank, depth: hy.depth,
                      self: hy.self, pagerank: hy.pagerank, change: hy.change, memory: hy.memory, ts: $now})
CREATE (i)-[:HAS_HYPOTHESIS]->(h)
