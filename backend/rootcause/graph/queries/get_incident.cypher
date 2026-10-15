// purpose: One incident with its alerts, ranked hypotheses, linked changes and journey impact
// algorithm: -
MATCH (i:Incident {id: $id})
OPTIONAL MATCH (a:Alert)-[:PART_OF]->(i)
WITH i, collect(DISTINCT {id: a.id, kind: a.kind, target: a.target, status: a.status, ts: a.ts, value: a.value}) AS alerts
OPTIONAL MATCH (i)-[:HAS_HYPOTHESIS]->(h:Hypothesis)
WITH i, alerts, collect(DISTINCT {target: h.target, score: h.score, rank: h.rank, depth: h.depth, self: h.self,
                                  pagerank: h.pagerank, change: h.change, memory: h.memory}) AS hyps
OPTIONAL MATCH (i)-[:CAUSED_BY]->(c:Change)-[:CHANGED]->(x)
WITH i, alerts, hyps, collect(DISTINCT {id: c.id, kind: c.kind, target: x.id, from_variant: c.from_variant, to: c.to,
                                        ts: c.ts, actor: c.actor}) AS changes
OPTIONAL MATCH (i)-[im:IMPACTED]->(j:Journey)
RETURN properties(i) AS incident, alerts, hyps, changes, collect(DISTINCT {journey: j.id, pct: im.pct}) AS impact
