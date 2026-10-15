// purpose: Append an investigation Step to an incident's trail (NEXT chain + CITED evidence nodes)
// algorithm: -
MATCH (i:Incident {id: $incident})
CREATE (s:Step {id: $id, n: $n, tool: $tool, args: $args, summary: $summary, ts: $ts})
CREATE (i)-[:INVESTIGATED_BY]->(s)
;
MATCH (prev:Step {id: $prev}), (s:Step {id: $id})
CREATE (prev)-[:NEXT]->(s)
;
MATCH (s:Step {id: $id})
UNWIND $cited AS cid
MATCH (x {id: cid})
WHERE NOT x:Step
MERGE (s)-[:CITED]->(x)
